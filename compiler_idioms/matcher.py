import sys
from typing import List
from icecream import ic

from compiler_idioms.anonymization import anonymize_instruction, anonymize_instructions_smda
# from compiler_idioms.disassembly.binja_disassembly import BinjaDisassembly
from compiler_idioms.disassembly.smda_disassembly import SMDADisassembly
#from compiler_idioms.idiom.implementations.division import SignedDivisionInstructionSequence
from compiler_idioms.idiom.implementations.divs_msvc import SignedDivisionInstructionSequence
from compiler_idioms.idiom.implementations.mods_msvc import SignedModuloInstructionSequence
#from compiler_idioms.idiom.implementations.division_unsigned import UnsignedDivisionInstructionSequence
from compiler_idioms.idiom.implementations.divu_msvc import UnsignedDivisionInstructionSequence
from compiler_idioms.idiom.implementations.divu86 import UnsignedDivisionInstructionSequence86
from compiler_idioms.idiom.implementations.multiplication import SignedMultiplicationInstructionSequence
from compiler_idioms.idiom.implementations.remainder_signed_todo import SignedRemainderInstructionSequence
#from compiler_idioms.idiom.implementations.mods import SignedModuloInstructionSequence
from compiler_idioms.idiom.implementations.modu_msvc import UnsignedModuloInstructionSequence
from compiler_idioms.instruction import Instruction
from compiler_idioms.match import Match



class Matcher:
    """
    """

    def __init__(self):
        self.idioms = [
            SignedModuloInstructionSequence(),
            UnsignedModuloInstructionSequence(),
            SignedDivisionInstructionSequence(),
            UnsignedDivisionInstructionSequence(),
            SignedMultiplicationInstructionSequence(),
        ]

    def find_idioms_in_file(self, file_path: str="", bv=None, buffer=None) -> List[Match]:
        """

        """
        ic("Path:", file_path)

        matches = []
        disassembly = SMDADisassembly(file_path, buffer=buffer)
        #disassembly = BinjaDisassembly(file_path, bv)
        for function in disassembly.next_disassembly_function():
            for i, instruction in enumerate(function):
                # if instruction.address >= 4226676 and instruction.address<=4226687:
                #     ic()
                #     ic(i)
                #     ic(instruction)
                    #4226683
                # if instruction.address == 4226683:
                #     ic()
                #     ic(instruction)
                #     ic(function[i:i + 100])
                # if instruction.matched:  # jump over matched instructions
                #     continue
                for idiom in self.idioms:
                    if instruction.matched:  # jump over matched instructions
                        continue
                    anonymized_first_instruction = anonymize_instruction(instruction)

                    if idiom.matches_first_instruction(anonymized_first_instruction):
                        anonymized_first_instructions, orig_constants, orig_registers = anonymize_instructions_smda(function[i:])
                        # if instruction.address == 0x004234b5:
                        #     print(function[i:])
                        #     print(anonymized_first_instructions)
                        #     print(orig_constants)
                        #     print(orig_registers)
                        # if anonymized_first_instruction.mnemonic == 'movsx':
                        #     ic(function[i:])
                        #     ic(anonymized_first_instructions)



                        if match := idiom.search(anonymized_first_instructions, orig_constants, orig_registers):
                            if not match:continue
                            #print(f"found match for idiom {match} on address {hex(match.address)}")
                            self._mark_instructions_as_matched(
                                function[i:i + match.length], match,
                                disassembly)  # +1? mark matched instructions to not to search for other idioms there
                            #yield match
                            matches.append(match)
        #disassembly.save_database()
        return matches

    @staticmethod
    def _mark_instructions_as_matched(instructions: List[Instruction], match: Match, disassembly):
        for instr in instructions:
            instr.matched = True
            #disassembly.set_tag(tag_name=f'compiler_idiom: {match.operation}', address=instr.address, text=f'{match.operand},{match.constant}')


if __name__ == "__main__":
    matcher = Matcher()
    matcher.find_idioms_in_file(sys.argv[1])
