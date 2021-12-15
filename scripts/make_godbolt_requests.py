import json
import math
import os
import multiprocessing
import multiprocessing.pool as mpp
from pathlib import Path
from random import randrange

import requests

import tqdm

def istarmap(self, func, iterable, chunksize=1):
    """starmap-version of imap
    """
    self._check_running()
    if chunksize < 1:
        raise ValueError(
            "Chunksize must be 1+, not {0:n}".format(
                chunksize))

    task_batches = mpp.Pool._get_tasks(func, iterable, chunksize)
    result = mpp.IMapIterator(self)
    self._taskqueue.put(
        (
            self._guarded_task_generation(result._job,
                                          mpp.starmapstar,
                                          task_batches),
            result._set_length
        ))
    return (item for chunk in result for item in chunk)


mpp.Pool.istarmap = istarmap

# To be replaced with local instance
GODBOLT_API_URL = "https://godbolt.org/api/"
GODBOLT_COMPILERS = [
    # "cg93",          # x64 GCC 9.3
    # "cg93-x86"       # x86 GCC 9.3
    "cg112-x86",       # x86 GCC 11.2
    "cl19_2015_u3_32", # x86 msvc v19.0
    "cl19_2015_u3_64", # x64 msvc v19.0
    "cg112",           # x64 GCC 11.2

]
GODBOLT_SETTINGS = ["O0", "O1", "O2", "O3", "Os"]


def get_godbolt_responses(ignore_existing_responses=False):
    for idiom in os.listdir("data"):
        if idiom.startswith("."): continue
        with open(Path("data", idiom, "meta.json"), "r") as jsonfile:
            content = jsonfile.read()
            # todo fix this
            content = content.replace("−", "-")
            meta = json.loads(content)
        with open(Path("data", idiom, "template.c"), "r") as templatefile:
            template = templatefile.read()
        print(f"Making requests for Idiom: {idiom}")
        values = set(sample_values(min_num=int(meta["MIN_VAL"]), max_num=int(meta["MAX_VAL"])))
        if idiom.endswith("u"): values = values | set(range(1,2049))
        with multiprocessing.Pool(processes=8) as pool:
            results = list(tqdm.tqdm(pool.istarmap(handle_value, [(v, template, ignore_existing_responses, idiom) for v in values]), total=len(values)))


def handle_value(value, template, ignore_existing_responses, idiom):
    make_godbolt_requests(
        template.replace("%VAL%", f"{value}"),
        ignore_existing_responses=ignore_existing_responses,
        value=value,
        idiom=idiom,
    )
    return True


def sample_values(min_num, max_num):
    yield min_num
    yield max_num
    if min_num <= 0 and max_num >= 0: yield 0
    # yield values from 0-100
    yield from range(max(-1024, min_num),min(1024, max_num),1)
    # positive powers of two
    for i in range(int(math.log2(max_num)) + 1):
        for j in range(-2, 3):

            res = 2 ** i + j
            if res>0:
                yield res
    # negative powers of two:
    if min_num < 0:
        for i in range(int(math.log2(abs(min_num))) + 1):
            for j in range(-2, 3):
                yield -(2 ** i + j)
    # yield some random integer values
    # for _ in range(100):
    #     yield randrange(min_num, max_num)


def make_godbolt_requests(c_code, ignore_existing_responses, value, idiom):
    for compiler in GODBOLT_COMPILERS:
        request_compiler = compiler
        m32 = False
        if "-" in compiler:
            m32 = True
            request_compiler = compiler.split("-")[0]
        for settings in GODBOLT_SETTINGS:
            request_settings = settings
            if compiler.startswith("cl"):
                request_settings = {
                    "O0": "Od",
                    "O1": "O1",
                    "O2": "O2",
                    "O3": "Ox",
                    "Os": "Os",
                }[settings]
            value_str = f'{value}'
            if value < 0:
                value_str = f'neg{value}'
            response_path = f"data/{idiom}/responses/{value_str}/{compiler}/{settings}/response.json"
            os.makedirs(Path(response_path).parent, exist_ok=True)
            if (not ignore_existing_responses) and os.path.exists(response_path):
                continue
            response = requests.post(
                GODBOLT_API_URL + "compiler/" + request_compiler + "/compile",
                params={"options": f"-{request_settings}" + (" -m32" if m32 else "")},
                data=c_code,
                headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'}
            )
            if response.status_code == 200:
                with open(response_path, "w") as outfile:
                    json.dump(response.json(), outfile)
            else:
                print(f"Request to Godbolt failed with status code {response.status_code} : {response.text}")
                # TODO Do we want to wait a few seconds and retry?


if __name__ == "__main__":
    get_godbolt_responses(ignore_existing_responses=False)




