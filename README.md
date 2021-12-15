# PIdARCI - Compiler Idioms

This repository contains the prototypical implementation of PIdARCI, Patterns to Identify And Revert Compiler Idioms.
PIdARCI detects, annotates and reverts compiler idioms in a given binary using anonymized pattern database and transformation rules.

You can find our paper introducing the PIdARCI approach [here](https://pstnet.ca).
The evaluation dataset can be found [here](https://github.com/fkie-cad/pidarci-dataset).

## Wait a minute... What are compiler idioms?

Compiler idioms are sequences of assembly instructions that compilers use instead of more readable but less efficient operations. For instance, for

```c
// int a, b
b = a / 388;
```
GCC does not use the `idiv reg_N, 388` instruction but the following instruction sequence:

```
movsx   rdx, eax
imul    rdx, rdx, 354224107
shr     rdx, 32
sar     edx, 5
sar     eax, 31
mov     ecx, eax
mov     eax, edx
sub     eax, ecx
```
We refer to such sequences as *compiler idioms*. To reconstruct the original high-level expression, `edx / 388`,  we need first to ~match~ those sequences in assembly and then ~reconstruct~ the original operation (division here) and original constant (`388` here).

Our current implementation covers compiler idioms for the following operations:
- integer division (signed/unsigned) by a constant
- integer modulo (signed/unsigned) by a constant
- integer multiplication (signed/unsigned) by a constant

## Compiler Idioms Detection and Reconstruction

In order to detect and revert (mark with the corresponding original expression) compiler idioms in a binary, run

```bash
# python main.py BINARY_PATH

cd compiler-idioms/
python main.py tests/evaluation/bin/divs_-1024_1024_gcc11_O0_x64
```

PIdARCI disassembles* the binary, matches compiler idioms using the database of anonymized assembly patterns, recovers the original operation and constant via transformation rules and finally produces an output in the following form:

```
...
Match at 0x00010d5e: eax / 388 (movsx; imul; shr; sar; sar; mov; mov; sub)
Match at 0x00010d8e: eax / 389 (movsx; imul; shr; add; sar; sar; mov; mov; sub)
Match at 0x00010dc0: eax / 390 (movsx; imul; shr; add; sar; sar; mov; mov; sub)
Match at 0x00010df2: eax / 391 (movsx; imul; shr; sar; sar; mov; mov; sub)
Match at 0x00010e22: eax / 392 (movsx; imul; shr; sar; sar; mov; mov; sub)
...
```

Each line of output corresponds to the single detected compiler idiom. For instance, the line `Match at 0x00010d5e: eax / 388 (movsx; imul; shr; sar; sar; mov; mov; sub)`  means that at the given address ~signed division by 388 - compiler idiom~ is found, where:
- `0x00010d5e` - address of the first assembly instruction where compiler idiom was detected;
- `eax` - original operand of the high-level expression
- `/` - original operation of the high-level expression
- `388` - original constant of the high-level expression
- `movsx; imul; shr; sar; sar; mov; mov; sub` - instruction mnemonics for the matched compiler idiom


## Limitations
- Our approach can only handle those idioms, that have their anonymized versions in the pattern database (generated for GCC 11.2 (O0-O3) and MSVC 19.29 (Od-Ox), x86 and x64). You should consider re-generating the database if you are using an alternative compiler version or the compiler implementation of the particular idiom has changed.
- The already existing pattern database covers only operations discussed above. To add new operations or compilers, you should also consider re-generating the database.
- New patterns may or may not require the manual derivation of new transformation rules.
- We do not handle nested compiler idioms.
- We do not handle non-sequential idioms (split on two and more parts by not-idiom instructions).


## Pattern Generation

*Usability of pattern generation is work in progress.*

In order to generate new patterns, the following steps are currently needed (relatively to the project root):

- To add support for a new operation (`NEW_OPERATION`):
	- Add a `NEW_OPERATION` folder to `data/`
	- Create `.../NEW_OPERATION/template.c` like the following:
	```c
	int func( int num) {
		int res;
		res = num <NEW_OPERATOR> %VAL%;
		return res;
	}

	int main(){
		return 0;
	}
	```
	- Fix the desired constant range for `%VAL%` in the file: `.../NEW_OPERATION/meta.json`, like e.g.:
	```json
	{"MIN_VAL": "−2147483648", "MAX_VAL": "2147483647"}
	```

- Run `PYTHONPATH=.. scripts\make_godbolt_requests.py` to generate the assembly snippets corresponding the line in template using Godbolt.
	- In case you want to add a new compiler version, add the desired version to the list of compilers in `make_godbolt_requests.py`.
- Run `PYTHONPATH=.. scripts\generate_patterns.sh` to use the GodBolt responses to create the anonymized assembly snippets and perform the clustering of the latter.
	- Update `scripts\combine_clusters_to_single_file.py` to consider the path to clusters for new idioms (`data/NEW_OPERATION/clusters`) as an input and name of the operation (`NEW_OPERATION`) to be used in pattern files.
	- The resulting (anonymized) patterns for single optimization levels are stored in one file, resulting in the following:
	```
	patterns/
		patterns-NEW_OPERATION-O0json
		...
		patterns-NEW_OPERATION-O3.json
	```

## How to reference this approach or prototype implementation
Please use the following citation referring to our paper when referencing this dataset:
```
@inproceedings{enders2021pidarci,
  title={PIdARCI: Using Assembly Instruction Patterns to Identify, Annotate, and Revert Compiler Idioms},
  author={Steffen Enders and Mariia Rybalka and Elmar Padilla},
  booktitle={2021 18th International Conference on Privacy, Security and Trust (PST)},
  year={2021},
  organization={IEEE}
}
```
