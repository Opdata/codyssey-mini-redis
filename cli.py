"""명령어 파싱 / 디스패치 / Redis 스타일 출력 포맷.

입력 한 줄을 받아 실행 결과 문자열을 돌려주는 것까지가 이 모듈의 책임이다.
표준 입출력 루프(REPL)는 main.py 가 담당한다.
"""

from store import MiniRedis, OOMError

PROMPT = "mini-redis> "

ERR_UNKNOWN = "(error) ERR unknown command '%s'"
ERR_ARGS = "(error) ERR wrong number of arguments for '%s' command"
ERR_NOT_INT = "(error) ERR value is not an integer or out of range"
ERR_OOM = "(error) OOM command not allowed when used_memory > 'maxmemory'"
ERR_CONFIG_PARAM = "(error) ERR Unknown CONFIG parameter '%s'"
ERR_CONFIG_SUB = "(error) ERR Unknown CONFIG subcommand '%s'"

EXIT_COMMANDS = ("EXIT", "QUIT")


def tokenize(line):
    """입력 한 줄을 토큰 목록으로 나눈다.

    공백으로 구분하되, 큰따옴표로 감싼 값은 공백을 포함해 하나로 묶는다.
    따옴표 자체는 토큰에서 제거한다.

        SET user:1 "Alice Kim"  ->  ['SET', 'user:1', 'Alice Kim']
    """
    tokens = []
    buf = []
    in_quotes = False

    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch.isspace() and not in_quotes:
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)

    if buf:
        tokens.append("".join(buf))

    return tokens


def parse_int(text):
    """정수로 변환한다. 실패하면 None.

    '12.5', 'abc', '' 처럼 정수가 아닌 입력을 모두 거른다.
    """
    try:
        return int(text)
    except ValueError:
        return None


def format_value(value):
    """문자열 값을 따옴표로 감싸 출력한다."""
    return '"%s"' % value


def format_integer(number):
    return "(integer) %d" % number


def format_keys(keys):
    """키 목록을 번호를 붙여 출력한다. 비어 있으면 (empty array)."""
    if not keys:
        return "(empty array)"

    lines = []
    for i, key in enumerate(keys, start=1):
        lines.append('%d. "%s"' % (i, key))

    return "\n".join(lines)


class CommandHandler:
    """한 줄 입력을 받아 실행 결과 문자열을 만든다."""

    def __init__(self, store=None):
        self.store = store if store is not None else MiniRedis()

    def execute(self, line):
        """입력 한 줄을 실행한다.

        반환값은 (출력 문자열 또는 None, 종료 여부) 튜플.
        빈 줄이면 출력 없이 계속 진행한다.
        """
        tokens = tokenize(line)
        if not tokens:
            return None, False

        name = tokens[0].upper()
        args = tokens[1:]

        if name in EXIT_COMMANDS:
            return None, True

        # 키 기반 명령 실행 전에 만료된 키들을 걷어낸다(능동 만료).
        self.store.active_expire()

        handler = self._lookup(name)
        if handler is None:
            return ERR_UNKNOWN % tokens[0], False

        try:
            return handler(name, args), False
        except OOMError:
            return ERR_OOM, False

    def _lookup(self, name):
        if name == "SET":
            return self._cmd_set
        if name == "GET":
            return self._cmd_get
        if name == "DEL":
            return self._cmd_del
        if name == "EXISTS":
            return self._cmd_exists
        if name == "DBSIZE":
            return self._cmd_dbsize
        if name == "KEYS":
            return self._cmd_keys
        if name == "EXPIRE":
            return self._cmd_expire
        if name == "TTL":
            return self._cmd_ttl
        if name == "CONFIG":
            return self._cmd_config
        if name == "INFO":
            return self._cmd_info

        return None

    # ------------------------------------------------------------------
    # String 명령어
    # ------------------------------------------------------------------

    def _cmd_set(self, name, args):
        if len(args) != 2:
            return ERR_ARGS % name

        self.store.set(args[0], args[1])

        return "OK"

    def _cmd_get(self, name, args):
        if len(args) != 1:
            return ERR_ARGS % name

        value = self.store.get(args[0])
        if value is None:
            return "(nil)"

        return format_value(value)

    def _cmd_del(self, name, args):
        if len(args) != 1:
            return ERR_ARGS % name

        return format_integer(self.store.delete(args[0]))

    def _cmd_exists(self, name, args):
        if len(args) != 1:
            return ERR_ARGS % name

        return format_integer(self.store.exists(args[0]))

    def _cmd_dbsize(self, name, args):
        if args:
            return ERR_ARGS % name

        return format_integer(self.store.dbsize())

    def _cmd_keys(self, name, args):
        if args:
            return ERR_ARGS % name

        return format_keys(self.store.keys())

    # ------------------------------------------------------------------
    # TTL 명령어
    # ------------------------------------------------------------------

    def _cmd_expire(self, name, args):
        if len(args) != 2:
            return ERR_ARGS % name

        seconds = parse_int(args[1])
        if seconds is None:
            return ERR_NOT_INT

        return format_integer(self.store.expire(args[0], seconds))

    def _cmd_ttl(self, name, args):
        if len(args) != 1:
            return ERR_ARGS % name

        return format_integer(self.store.ttl(args[0]))

    # ------------------------------------------------------------------
    # 메모리 관리 명령어
    # ------------------------------------------------------------------

    def _cmd_config(self, name, args):
        if len(args) != 3:
            return ERR_ARGS % name

        subcommand = args[0].upper()
        if subcommand != "SET":
            return ERR_CONFIG_SUB % args[0]

        param = args[1].lower()
        if param != "maxmemory":
            return ERR_CONFIG_PARAM % args[1]

        value = parse_int(args[2])
        if value is None or value < 0:
            return ERR_NOT_INT

        self.store.config_set_maxmemory(value)

        return "OK"

    def _cmd_info(self, name, args):
        if len(args) > 1:
            return ERR_ARGS % name
        if args and args[0].lower() != "memory":
            return ERR_ARGS % name

        used, maxmem, evicted = self.store.info_memory()

        return "used_memory:%d\nmaxmemory:%d\nevicted_keys:%d" % (
            used,
            maxmem,
            evicted,
        )
