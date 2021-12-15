import ctypes

from typing import List, Dict, Tuple

from icecream import ic

from compiler_idioms.idiom.instruction_sequence import InstructionSequence
from compiler_idioms.idiom.utils.magic import compute_magic_numbers_if_not_exists
from compiler_idioms.idiom.utils.pattern_utils import load_pattern_sequences_for_operation
from compiler_idioms.instruction import from_anonymized_pattern, Instruction
from compiler_idioms.match import Match
from config import ROOT

HEX_BASE = 16
# ic.disable()


class SignedModuloInstructionSequence(InstructionSequence):
    MUL = {'imul', 'mul'}
    RIGHT_SHIFT = {'sar', 'shr'}
    DIV = {'idiv', 'div'}

    def __init__(self):
        self.abbrev_operation_name = "mods"
        self.operation_name = "modulo"
        sequences = load_pattern_sequences_for_operation(self.abbrev_operation_name)
        self.magic_table = compute_magic_numbers_if_not_exists()
        super().__init__(sequences)

    def search(
            self,
            sequence: List[Instruction],
            original_constants: Dict[str, str],
            original_registers: Dict[str, str],
    ) -> Match:
        if match := super().search(sequence, original_constants, original_registers):
            return self.handle_match(
                match, original_constants, original_registers, sequence
            )

    def handle_match(
            self,
            match: Match,
            original_constants: Dict[str, str],
            original_registers: Dict[str, str],
            sequence,
    ):
        match.operation = self.operation_name
        match.operand = self._get_register_operand(original_registers)
        if not (original_constants):
            # todo handle 03 -1
            match.constant = None
            return match
        # TODO handle idiv
        # todo let unsigned div to take care about shr reg const
        if match.length == 1 and sequence[0].mnemonic == 'shr': return None
        div = [x for x in sequence if x.mnemonic in self.DIV]
        if div:
            return self.handle_patterns_with_div(match, original_constants, sequence, original_registers)
        mul = [x for x in sequence if x.mnemonic in self.MUL]
        if not mul:
            match = self.handle_powers_of_two(match, original_constants, sequence)
            return match
        match = self.handle_magic_numbers_division(match, original_constants, original_registers,
                                                   sequence)
        return match

    def handle_patterns_with_div(self, match, original_constants, sequence, original_registers):
        const = int(original_constants['const_0'], HEX_BASE)
        original_constant = ctypes.c_int32(const).value
        # if original_constant < 0:
        #     original_constant = -original_constant
        match.constant = original_constant
        # if match.constant < 0:
        #     match.constant = -match.constant
        if match.sequence[-1].mnemonic in self.DIV:
            if self._remainder_register_is_copied_after_div(match, sequence, original_registers):
                match.operation = 'modulo'
            else:
                match.operation = 'division'
        return match

    def _remainder_register_is_copied_after_div(self, match, sequence, original_registers):

        if len(sequence) > len(match.sequence) and match:
            next_after_div = sequence[len(match.sequence)]
            if next_after_div.mnemonic == 'mov':
                source = next_after_div.operands[-1]
                if source in original_registers and original_registers[source] == 'edx':
                    return True
        return False


    def handle_powers_of_two(
                self,

                match: Match,
                original_constants: Dict[str, str],
                sequence: List[Instruction],
        ):
            """
            ...
            shr reg, const
            ...
            reg/2**const
            """
            constant = None
            for i in sequence:
                if i.mnemonic == 'or' and self._is_constant(i.operands[-1]):
                    constant = i.operands[1]
                    if ctypes.c_int32(int(original_constants.get(constant), HEX_BASE)).value > 0:
                        continue

                    match.constant = -(ctypes.c_int32(int(original_constants.get(constant), HEX_BASE)).value)
                    ic()
                    ic(match.constant)
                    return match
            for i in sequence:
                if i.mnemonic == "and":
                    constant = i.operands[1]
                    match.constant = int(original_constants.get(constant), HEX_BASE) + 1
                    break
            if not constant:
                match.constant = None
                return match
            return match

    def handle_magic_numbers_division(
            self,
            match: Match,
            original_constants: Dict[str, str],
            original_registers: Dict[str, str],
            sequence: List[Instruction],
    ):
        match.constant = None
        match.constant = self._get_original_constant_from_magic(original_constants, original_registers, sequence)
        return match

    def _get_register_operand(self, original_registers: Dict[str, str]):
        return original_registers.get("reg_1", [])

    def _get_original_constant_from_magic(
            self, original_constants: Dict[str, str], original_registers: Dict[str, str], sequence: List[Instruction]
    ) -> int:
        magic, imul_index = self._get_mul_constant_and_position(sequence, original_constants)
        if not magic:
            magic = self._backtrack_magic_number(imul_index, sequence, original_constants, original_registers)
        power = self._accumulate_shift_amount(sequence, original_constants)
        quotient = self._lookup(magic, power)
        if ctypes.c_int32(magic).value < 0 and not quotient:
            # case 7
            unsigned_magic = ctypes.c_uint32(magic).value
            quotient = self._lookup(unsigned_magic, power)
            if not quotient:
                negative_magic = ctypes.c_int32(magic).value
                quotient = self._lookup(negative_magic, power)
        return quotient

    def _lookup(self, magic: int, power: int) -> int:
        quotient = self._search_magic_table(magic, power)
        if not quotient:
            quotient = self._search_magic_table(magic, power + 32)
        return quotient

    def _search_magic_table(self, magic: int, power: int) -> int:
        quotient = self.magic_table.get((magic, power))
        return quotient

    def _get_mul_constant_and_position(self, sequence: List[Instruction], original_constants: Dict[str, str]) -> Tuple[
        int, int]:
        magic = 0
        first_mul_index = 0
        for i, instr in enumerate(sequence):
            if instr.mnemonic in self.MUL:
                first_mul_index = i
                for op in instr.operands:
                    if self._is_constant(op):
                        magic = int(original_constants.get(op), HEX_BASE)
                        return magic, first_mul_index
                return 0, first_mul_index
        return magic, first_mul_index

    def _accumulate_shift_amount(self, sequence: List[Instruction], original_constants: Dict[str, str]) -> int:
        result = 0
        for instr in sequence:
            if instr.mnemonic in self.RIGHT_SHIFT:
                for op in instr.operands:
                    if self._is_constant(op):
                        val = int(original_constants.get(op), HEX_BASE)
                        if val != 0x1f:
                            result += int(original_constants.get(op), HEX_BASE)
        return result

    def _backtrack_magic_number(self, imul_index: int, sequence: List[Instruction], original_constants: Dict[str, str],
                                original_registers: Dict[str, str]) -> int:
        magic_number = 0
        mul_instr = sequence[imul_index]
        for anonymized_operand in mul_instr.operands:
            if anonymized_operand not in original_registers:
                register = 'eax'
                lower = 'ax'
            else:
                register = original_registers[anonymized_operand]
                lower = register[1:]
            if len(mul_instr.operands) == 1 and not register.endswith('ax') and not register.endswith('dx'):
                register = 'eax'
                lower = 'ax'

            for i in range(imul_index - 1, -1, -1):
                current_instr = sequence[i]
                if current_instr.mnemonic == 'mov':
                    destination = current_instr.operands[0]
                    #todo hotfix to rconst_n, remove
                    if destination not in original_registers:
                        continue
                    destination_register = original_registers.get(destination)
                    if destination_register == register or destination_register.endswith(lower):
                        if self._is_constant(current_instr.operands[-1]):
                            magic_number = int(original_constants.get(current_instr.operands[-1]), HEX_BASE)
                            return magic_number
                        else:
                            register = original_registers.get(current_instr.operands[-1])

        return magic_number

    @staticmethod
    def _is_constant(anonymized_operand: str) -> bool:
        return anonymized_operand.startswith("const")


if __name__ == "__main__":
    idiom = SignedModuloInstructionSequence()
    print(idiom.magic_table)
