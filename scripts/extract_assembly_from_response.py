import json
import pathlib
import re
from typing import Dict, Union
import tqdm
# import sys
# sys.path.append('..')

from config import DATA_DIR
from compiler_idioms.utils import write_json_data, read_json_data, get_operation_dirs

from anonymize_assembly import REGISTERS

GODBOLT_RESPONSE_DIR = "responses"
ASM_DIR = "asm"
LINE = 3

INSTR_REGEX = r"\s*(\w+)(.*)"
OP_REGEX = r"\s*([a-z]+|\d+)"


def extract_assembly_from_godbolt_responses() -> None:
    """
    For all the operations in data directory:
        extracts assembly lines that are related to pattern and writes them to separate file

    e.g.:
    godbolt response from file ROOT/data/mods/response/-2/cg93/-O0/response.json is parsed,
    assembly lines corresponding to the pattern x %(mods) 3 (line 3 in source code) are extracted
    and put to ROOT/data/mods/asm/-2/cg93/-O0/asm.json


    """
    for op_dir in tqdm.tqdm(get_operation_dirs()):
        response_dir = DATA_DIR / op_dir / GODBOLT_RESPONSE_DIR
        for infile in filter(pathlib.Path.is_file, response_dir.glob("**/*")):
            if infile.name == ".DS_Store": continue
            data = read_json_data(infile)
            outfile = (
                    DATA_DIR
                    / op_dir
                    / ASM_DIR
                    / infile.relative_to(response_dir).parent
                    / "asm.json"
            )
            asm_data = _parse_asm_key(data)
            write_json_data(asm_data, outfile)


def _parse_asm_key(data: Dict, operation=None) -> Dict:
    """
    parse data from asm key in godbolt response:
    {
    ...
    'asm': [
        {'text': 'func:', 'source': None, 'labels': []},
        {'text': '        test    edi, edi', 'source': {'file': None, 'line': 3},
        ...
    }
    The first item in the list stays for function name and does not contain assembly.
    """
    parsed_asm_lines = []
    asm_text = []

    for line in data["asm"][1:]:
        if src := line["source"]:
            # for modu msvc on -O1, remainder is copied from edx to eax, but this copy lies on line 4, not 3
            # the pattern lying on line 3 is completely identical to those of divu
            if src["line"] != LINE:#and not (src['line'] == LINE+1 and asm_text and (asm_text[-1].startswith("div") or asm_text[-1].startswith('idiv'))and line['text'].endswith("edx")):
                continue

            asm = line["text"]
            if ";" in asm:
                asm = asm.split(";")[0].strip()
            if "[0+" in asm:
                asm = asm.replace("0+", "")
            if matched := re.match(INSTR_REGEX, asm):
                l = asm.strip()
                mnemonic = matched.group(1)

                operands = []
                if operands_str := matched.group(2):
                    operands = [_prettify_operand(op) for op in operands_str.split(",")]
                    if mnemonic in {"shr", 'shl', 'sar', 'sal'} and len(operands) == 1:
                        """
                        shr eax is the same as shr eax, 1
                        godbolt uses the first representation,
                        smda the second.
                        we change godbolt's shr eax to shr eax, 1
                        """
                        operands.append(1)
                        l+= ", 1"

                    if mnemonic in {"jns", "js", "jmp", "je", "jne", "ja", "jb", "jae", "jbe", "jge", "jle"}:
                        #asm_text[-1] = f"{mnemonic}"
                        #asm_text.append(f"{mnemonic}")
                        l = mnemonic
                        operands = []

                parsed_asm_lines.append(
                    {"opcode": mnemonic, "operands": operands, "text": asm.strip()}
                )

            asm_text.append(l)
    # we store original assembly snippet of the pattern in case any mistake happens during parsing

    # we delete the first instruction if if is a mov reg, loc
    if len(parsed_asm_lines) > 1 and parsed_asm_lines[0]["opcode"] == "mov" and re.match(f"({'|'.join(sorted(REGISTERS, key=len))}), (?P<loc>((d*q*word|byte|(D*WORD)|BYTE)+\s(ptr|PTR)\s*(\_?[a-zA-Z]+\$)?\s*\[(esp|ebp|rsp|rbp)+\s*(-|\+)*\s*([0-9]|0x[A-Fa-f0-9]+)*\]))", ", ".join(map(str, parsed_asm_lines[0]["operands"]))):
        parsed_asm_lines = parsed_asm_lines[1:]
        asm_text = asm_text[1:]
    # we also delete the last instruction if it is a mov loc, reg
    if len(parsed_asm_lines) > 1 and parsed_asm_lines[-1]["opcode"] == "mov" and re.match(f"(?P<loc>((d*q*word|byte|(D*WORD)|BYTE)+\s(ptr|PTR)\s*(\_?[a-zA-Z]+\$)?\s*\[(esp|ebp|rsp|rbp)+\s*(-|\+)*\s*([0-9]|0x[A-Fa-f0-9]+)*\])), ({'|'.join(sorted(REGISTERS, key=len))})", ", ".join(map(str, parsed_asm_lines[-1]["operands"]))):
        parsed_asm_lines = parsed_asm_lines[:-1]
        asm_text = asm_text[:-1]
    return {"parsed": parsed_asm_lines, "text": asm_text}


def _prettify_operand(operand: str) -> Union[int, str]:
    """Strip whitespaces from string operands;
    convert numeric strings to integers
    """
    prettified = operand.strip()
    if str.isnumeric(prettified):
        return int(prettified)
    return prettified


if __name__ == "__main__":
    extract_assembly_from_godbolt_responses()
    # path =DATA_DIR / 'modu/responses/132/cl19_2015_u3_32/Os/response.json'
    # with path.open('r') as f:
    #     data = json.load(f)
    #     print(json.dumps(data['asm'], indent=4))
    #     res =_parse_asm_key(data)
    #     print(json.dumps(res, indent=4))

