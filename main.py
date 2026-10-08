"""Mini Redis 실행 진입점 (REPL).

    python3 main.py

프롬프트를 띄우고 한 줄씩 입력을 받아 실행 결과를 출력한다.
exit / quit 또는 EOF(Ctrl+D)로 종료한다.
"""

from cli import PROMPT, CommandHandler


def repl():
    """입력 -> 실행 -> 출력을 반복한다."""
    handler = CommandHandler()

    while True:
        try:
            line = input(PROMPT)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        output, should_exit = handler.execute(line)
        if output is not None:
            print(output)
        if should_exit:
            break


if __name__ == "__main__":
    repl()
