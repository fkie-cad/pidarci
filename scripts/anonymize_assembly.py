import os
import json
import math
import tqdm
import re
from pathlib import Path
from itertools import count


REGISTERS = [
    # Registers:
    "al", "bl", "cl", "dl",
    "ah", "bh", "ch", "dh",
    "ax", "bx", "cx", "dx", "sp", "bp", "si", "di",
    "eax", "ebx", "ecx", "edx", "esp", "ebp", "esi", "edi",
    # 64bit Registers
    "rax", "rbx", "rcx", "rdx", "rsp", "rbp", "rsi", "rdi", "rip",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
    "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d",
    "r8w", "r9w", "r10w", "r11w", "r12w", "r13w", "r14w", "r15w",
    "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b",
    "sil", "dil", "bpl", "spl",
    # Segment Registers
    "cs", "ds", "es", "fs", "gs", "ss",
    # Extended Registers
    "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7", "xmm8", "xmm9", "xmm10", "xmm11", "xmm12", "xmm13", "xmm14", "xmm15",
    "ymm0", "ymm1", "ymm2", "ymm3", "ymm4", "ymm5", "ymm6", "ymm7", "ymm8", "ymm9", "ymm10", "ymm11", "ymm12", "ymm13", "ymm14", "ymm15",
    # Debug Registers
    "dr0", "dr1", "dr2", "dr3", "dr4", "dr5", "dr6", "dr7",
    # Control Registers
    "cr0", "cr1", "cr2", "cr3", "cr4", "cr5", "cr6", "cr7", "cr8",
    # Test Registers
    "tr3", "tr4", "tr5", "tr6", "tr7"
]

def anonymize():
    for idiom in os.listdir("data"):
        if idiom.startswith("."): continue
        if idiom == "checkeven": continue
        print(f"Anonymizing Idiom: {idiom}")
        for value in tqdm.tqdm(os.listdir(f"data/{idiom}/asm")):
            if value == ".DS_Store": continue
            for compiler in os.listdir(f"data/{idiom}/asm/{value}"):
                if compiler == ".DS_Store": continue
                for optimization_level in os.listdir(f"data/{idiom}/asm/{value}/{compiler}"):
                    if optimization_level == ".DS_Store": continue
                    path = f"data/{idiom}/asm/{value}/{compiler}/{optimization_level}/asm.json"
                    with open(path, "r") as infile:
                        data = json.load(infile)
                    anonymize_data(data)
                    new_path = f"data/{idiom}/asm/{value}/{compiler}/{optimization_level}/asm_anon.json"
                    if os.path.exists(new_path) and os.path.isfile(new_path): os.remove(new_path)
                    with open(new_path, "w") as outfile:
                        json.dump(data, outfile, indent=4, sort_keys=True)


def anonymize_data(data):
    # mask dword stuff
    dword_regex = r"(?P<loc>DWORD PTR\s*(\_[a-zA-Z]+\$)?\s*\[[^\]]*\])"
    dword_regex = r'(?P<loc>((d*q*word|byte|(D*WORD)|BYTE)+\s(ptr|PTR)\s*(\_?[a-zA-Z]+\$)?\s*\[(esp|ebp|rsp|rbp)+\s*(-|\+)*\s*([0-9]|0x[A-Fa-f0-9]+)*\]))'
    data["locations"] = {}
    dword_replacements = dword_names()
    for i, l in enumerate(data["text"]):
        if match := re.search(dword_regex, l):
            if match.group("loc") in data["locations"].values(): continue
            if l.startswith("lea "): continue
            data["locations"][next(dword_replacements)] = match.group("loc")
    if data["locations"]: replace_in_data({v: k for k, v in {**data["locations"]}.items()}, data)
    # mask constants
    data["constants"] = {}
    const_replacements = const_names()
    complete_text = "\n".join(data["text"])
    # for match in re.finditer(f"(?P<const>-?\d+)(?![^\[]*\])", complete_text):
    for match in re.finditer(f"(?P<const>(loc)?-?\d+)", complete_text):
        const = match.group("const")
        if const.startswith("loc"): continue
        if const not in data["constants"].values():
            data["constants"][next(const_replacements)] = const
    # mask registers
    register_replacements = get_replacement_dict(REGISTERS, register_names(), data)
    data["registers"] = {v: k for k, v in register_replacements.items()}
    # remove duplicate whitespaces
    def repl_dword(text):
        if text.startswith("lea"):
            return text.replace("DWORD PTR", "")
        return text
    data["text"] = [
        re.sub(' +', ' ', repl_dword(l)) for l in data["text"]
    ]
    for instr in data["parsed"]:
        instr["text"] = repl_dword(instr["text"])
        instr["text"] = re.sub(' +', ' ', instr["text"])
    # make replacements, also replace sal by shl
    replace_in_data({v:k for k,v in {**data["constants"], **data["registers"], "shl": "sal"}.items()}, data)


def get_replacement_dict(candidates, replacements, data):
    #complete_text = "\n".join(data["text"])
    complete_text = "\n".join((" ".join(line.split(" ")[1:]) for line in data["text"]))
    result = {}
    for match in re.finditer(f"({'|'.join(candidates)})", complete_text):
        register = complete_text[match.span()[0]: match.span()[1]]
        if register not in result:
            result[register] = next(replacements)
    return result


def replace_in_data(replacement_dict, data):
    search_regex = f"(?:^|(?<=[^a-z]))(?P<reg>{'|'.join(sorted(map(re.escape, replacement_dict.keys()), key=len, reverse=True))})(?=$|[^a-z])"
    def get_replacement(match):
        return replacement_dict[match.group('reg')]
    data["text"] = [
        re.sub(search_regex, get_replacement, l) for l in data["text"]
    ]
    for instr in data["parsed"]:
        instr["operands"] = [re.sub(search_regex, get_replacement, str(o)) for o in instr["operands"]]
        instr["operands"] = [o.replace("DWORD PTR", "").strip() for o in instr["operands"]]
        instr["text"] = re.sub(search_regex, get_replacement, instr["text"])
        instr["opcode"] = re.sub(search_regex, get_replacement, instr["opcode"])

def register_names():
    for i in count(0):
        yield f"reg_{i}"

def const_names():
    for i in count(0):
        yield f"const_{i}"

def dword_names():
    for i in count(0):
        yield f"loc{i}"


if __name__ == "__main__":
    anonymize()
