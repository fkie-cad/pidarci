import os

import pathlib
import shutil
from collections import defaultdict
from typing import Dict, Tuple

from icecream import ic

from compiler_idioms.utils import get_operation_dirs, read_json_data, write_json_data

ANONYMIZED_DATA_DIR = "asm"
CLUSTER_DIR = "clusters"
os.environ["PYTHONHASHSEED"] = "10"

def cluster():
    for op_dir in get_operation_dirs():
        ic(op_dir)
        anonymized_data_dir = op_dir / ANONYMIZED_DATA_DIR
        optimization_clusters = _init_dicts_for_clusters_for_optimization_levels()
        pattern_dict = {}
        parsed_pattern_dict = {}
        operation = op_dir.name
        cluster_dir = op_dir / CLUSTER_DIR
        for infile in filter(
                pathlib.Path.is_file, anonymized_data_dir.glob("**/*anon*")
        ):
            _update_clusters_with_pattern_and_data(
                infile, pattern_dict, optimization_clusters, anonymized_data_dir, parsed_pattern_dict
            )
        counter = 0
        for opt, clusters in optimization_clusters.items():
            for pattern, cluster in clusters.items():
                path = cluster_dir / opt / f"cluster_{counter}.json"
                if path.exists():
                    path.unlink()
                counter += 1
                result = _generate_data_for_single_optimization_cluster(
                    operation, pattern, pattern_dict, cluster, parsed_pattern_dict
                )
                write_json_data(result, path)


def _get_metadata_from_file_name(
        infile: pathlib.Path, anonymized_data_dir: pathlib.Path
) -> Tuple[int, str, str]:
    relative_path = infile.relative_to(anonymized_data_dir)
    const_str = relative_path.parts[0]
    if "neg" in const_str:
        const_str = f'-{const_str.split("-")[1]}'
    original_constant = int(const_str)
    compiler = relative_path.parts[1]
    optimization = relative_path.parts[2]
    return original_constant, compiler, optimization


def _update_clusters_with_pattern_and_data(
        infile: pathlib.Path,
        pattern_dict: Dict,
        optimization_clusters: Dict,
        anonymized_data_dir: pathlib.Path,
        parsed_pattern_dict: Dict
):
    data = read_json_data(infile)
    original_constant, compiler, optimization = _get_metadata_from_file_name(
        infile, anonymized_data_dir
    )
    pattern = _get_pattern(data)
    #ic(pattern)
    parsed_pattern_dict[pattern] = data['parsed']
    if pattern not in pattern_dict:
        pattern_dict[pattern] = data["text"]

    optimization_clusters[optimization][pattern].append(
        {
            "original constant": original_constant,
            "pattern constants": _get_constants(data),
            "opt": optimization
        }
    )


def _generate_data_for_single_optimization_cluster(
        operation: str, pattern: Tuple, pattern_dict: Dict, cluster: Dict, parsed_pattern_dict
) -> Dict:
    result = {
        "operation": operation,
        "pattern": pattern_dict[pattern],
        "parsed": parsed_pattern_dict[pattern],
        "cluster size": len(cluster),
        "cluster": sorted(cluster, key=lambda x: x["original constant"]),
    }
    # _reset_unchanged_constants_to_original_values(result)
    return result


def _init_dicts_for_clusters_for_optimization_levels() -> Dict[str, Dict]:
    clusters_opt0 = defaultdict(list)
    clusters_opt1 = defaultdict(list)
    clusters_opt2 = defaultdict(list)
    clusters_opt3 = defaultdict(list)
    clusters_opts = defaultdict(list)
    opts = {
        "O0": clusters_opt0,
        "O1": clusters_opt1,
        "O2": clusters_opt2,
        "O3": clusters_opt3,
        "Os": clusters_opts,
    }
    return opts


def _get_pattern(data: Dict) -> Tuple[str]:
    text = data["text"]
    pattern = tuple(text)
    return pattern


def _get_constants(data: Dict) -> Dict:
    return {name: int(const) for name, const in data["constants"].items()}


def _reset_unchanged_constants_to_original_values(result_dict: Dict):
    first_cluster = result_dict["cluster"][0]
    constants = first_cluster["pattern constants"].keys()

    for const in constants:
        const_val = first_cluster["pattern constants"][const]
        if all(
                [c["pattern constants"][const] == const_val for c in result_dict["cluster"]]
        ):
            result_dict['pattern'] = [line.replace(const, str(const_val)) for line in result_dict["pattern"]]


if __name__ == "__main__":
    cluster()
