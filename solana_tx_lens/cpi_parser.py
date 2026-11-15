import re
from typing import List, Tuple
from .models import CPIInvocation

INVOKE_RE = re.compile(r"^Program (\w+) invoke \[(\d+)\]")
SUCCESS_RE = re.compile(r"^Program (\w+) success")
FAILED_RE = re.compile(r"^Program (\w+) failed: (.+)")
CONSUMED_RE = re.compile(r"^Program (\w+) consumed (\d+) of (\d+) compute units")


def parse_cpi_tree(logs: List[str]) -> List[CPIInvocation]:
    """
    Parses Solana runtime simulation logs into a nested tree of CPIInvocation objects.
    Extracts program IDs, execution depths, consumed compute units, and failures.
    """
    roots: List[CPIInvocation] = []
    stack: List[CPIInvocation] = []

    for line in logs:
        line = line.strip()

        # 1. Program invoke [depth]
        m_invoke = INVOKE_RE.match(line)
        if m_invoke:
            prog_id = m_invoke.group(1)
            depth = int(m_invoke.group(2))
            node = CPIInvocation(program_id=prog_id, depth=depth)

            if depth == 1:
                roots.append(node)
                stack = [node]
            else:
                while len(stack) >= depth:
                    stack.pop()
                if stack:
                    stack[-1].children.append(node)
                stack.append(node)
            continue

        if not stack:
            continue

        curr = stack[-1]
        curr.logs.append(line)

        # 2. Consumed compute units
        m_consumed = CONSUMED_RE.match(line)
        if m_consumed:
            cus = int(m_consumed.group(2))
            curr.consumed_cus = cus
            continue

        # 3. Success
        m_success = SUCCESS_RE.match(line)
        if m_success:
            if stack and stack[-1].program_id == m_success.group(1):
                stack.pop()
            continue

        # 4. Failure
        m_failed = FAILED_RE.match(line)
        if m_failed:
            curr.failed = True
            curr.error_message = m_failed.group(2)
            if stack and stack[-1].program_id == m_failed.group(1):
                stack.pop()
            continue

    return roots
