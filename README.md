# Mini Redis

해시맵, 이중 연결 리스트, 최소 힙을 직접 구현해서 만든 CLI 기반 In-Memory Key-Value 저장소.
LRU 방식 메모리 제거와 TTL 만료를 지원한다.

## 실행

```bash
python3 main.py
```

- Python 3.8 이상
- 외부 라이브러리 없음
- `exit` 또는 `quit`으로 종료

## 지원 명령어

| 분류 | 명령어 | 응답 |
|---|---|---|
| String | `SET key value` | `OK` |
| | `GET key` | `"value"` / `(nil)` |
| | `DEL key` | `(integer) 1` / `(integer) 0` |
| | `EXISTS key` | `(integer) 1` / `(integer) 0` |
| | `DBSIZE` | `(integer) N` |
| | `KEYS` | 키 목록 / `(empty array)` |
| 메모리 | `CONFIG SET maxmemory bytes` | `OK` (0이면 무제한) |
| | `INFO memory` | `used_memory` / `maxmemory` / `evicted_keys` |
| TTL | `EXPIRE key seconds` | `(integer) 1` / 키가 없으면 `(integer) 0` |
| | `TTL key` | 남은 초 / TTL 미설정 `-1` / 키 없음 `-2` |

값은 따옴표 없이 쓰거나(`Bob`) 큰따옴표로 감싸서(`"Alice Kim"`) 입력한다.

## 동작 규칙

- **LRU**: `SET`과 `GET`이 성공하면 해당 키가 최근 사용으로 갱신된다.
- **메모리 제한**: `used_memory = Σ(len(utf8(key)) + len(utf8(value)))`로 계산한다. 자료구조 오버헤드는 포함하지 않는다.
  - `maxmemory`를 넘으면 가장 오래 사용되지 않은 키부터, 한도 이하가 될 때까지 제거한다.
  - 제거된 키는 `evicted_keys`에 누적된다.
  - 키+값 하나가 그 자체로 `maxmemory`를 넘으면 저장하지 않고 OOM 에러를 낸다.
- **TTL**: 모든 키 명령은 실행 전에 만료 여부를 확인한다. 만료된 키는 삭제한 뒤 없는 키로 처리한다.
  - 만료된 키를 `GET`하면 `(nil)`을 반환하고, LRU는 갱신하지 않는다.
  - `SET`으로 덮어쓰면 TTL이 초기화된다.
  - `EXPIRE`의 seconds가 0 이하이면 즉시 만료된다.
  - `DEL`은 데이터, TTL, LRU에서 모두 제거한다.

## 에러 형식

```
(error) ERR unknown command '<cmd>'
(error) ERR wrong number of arguments for '<cmd>' command
(error) ERR value is not an integer or out of range
(error) OOM command not allowed when used_memory > 'maxmemory'
```

## 구조

```
main.py                         REPL 진입점
cli.py                          명령어 파싱 / 실행 / 출력 포맷
store.py                        저장소 (해시맵 + LRU + TTL + 메모리 관리)
structures/doublyLinkedList.py  이중 연결 리스트
structures/hashMap.py           해시맵 (체이닝)
structures/heap.py              최소 힙
```

| 자료구조 | 구현 내용 | 역할 |
|---|---|---|
| 이중 연결 리스트 | `prev`/`next`/`data` 노드, 삽입·삭제·이동 O(1) | LRU 사용 순서, 해시맵 체인 |
| 해시맵 | 해시 함수 직접 설계(djb2), 체이닝, 로드 팩터 0.75 초과 시 2배 확장 | 키 → 값 조회 |
| 최소 힙 | `_heapify_up`/`_heapify_down`, `(expire_at, key)` 요소 | 가장 빠른 만료 키 탐색 |

## 제약 사항

- `dict`, `set`, `collections`를 사용하지 않는다. 해시맵을 직접 구현했다.
- 자료구조마다 독립된 파일로 분리했다.
- 네트워크, 영속성, 복잡한 자료형(List/Set/Sorted Set), 동시성은 구현 범위 밖이다.

## 시연 명령어

프로젝트 루트에서 그대로 복사해 실행한다. 출력에서 프롬프트(`mini-redis>`)는 생략했다.

**1. String 명령어 6종**
```bash
printf 'SET user:1 "Alice"\nGET user:1\nEXISTS user:1\nDBSIZE\nKEYS\nDEL user:1\nGET user:1\nKEYS\nexit\n' | python3 main.py
```
→ `OK` / `"Alice"` / `(integer) 1` / `(integer) 1` / `1. "user:1"` / `(integer) 1` / `(nil)` / `(empty array)`

**2. LRU 자동 제거 + INFO memory**
```bash
printf 'CONFIG SET maxmemory 30\nSET user:1 "Alice"\nSET user:2 "Bob"\nSET user:3 "Charlie"\nGET user:1\nINFO memory\nKEYS\nexit\n' | python3 main.py
```
→ 누적 33 > 30이 되어 가장 오래된 `user:1`이 제거된다. `(nil)` / `used_memory:22` / `maxmemory:30` / `evicted_keys:1` / `1. "user:2"` / `2. "user:3"`

**3. GET이 LRU 순서를 갱신하는지**
```bash
printf 'CONFIG SET maxmemory 30\nSET user:1 "Alice"\nSET user:2 "Bob"\nGET user:1\nSET user:3 "Charlie"\nKEYS\nexit\n' | python3 main.py
```
→ `GET user:1`로 user:1이 최근 키가 되어, 이번에는 `user:2`가 제거된다. `1. "user:3"` / `2. "user:1"`

**4. OOM / maxmemory 0 무제한**
```bash
printf 'CONFIG SET maxmemory 5\nSET verylongkey "verylongvalue"\nCONFIG SET maxmemory 0\nSET a "1"\nSET b "2"\nSET c "3"\nDBSIZE\nINFO memory\nexit\n' | python3 main.py
```
→ `(error) OOM command not allowed when used_memory > 'maxmemory'` / … / `(integer) 3` / `used_memory:6` / `maxmemory:0` / `evicted_keys:0`

**5. TTL 규칙 (대기 없이 확인)**
```bash
printf 'TTL nokey\nEXPIRE nokey 10\nSET k "v"\nTTL k\nEXPIRE k 100\nTTL k\nSET k "v2"\nTTL k\nEXPIRE k 0\nEXISTS k\nexit\n' | python3 main.py
```
→ `-2` (없는 키) / `0` / `OK` / `-1` (TTL 없음) / `1` / `100` / `OK` / `-1` (덮어쓰기로 초기화) / `1` (즉시 만료) / `0`

**6. TTL 실제 만료 (2.5초 대기)**
```bash
(printf 'SET user:2 "Bob"\nEXPIRE user:2 2\nTTL user:2\n'; sleep 2.5; printf 'GET user:2\nTTL user:2\nexit\n') | python3 main.py
```
→ `OK` / `(integer) 1` / `(integer) 2` / `(nil)` / `(integer) -2`

**7. 에러 처리**
```bash
printf 'HELLO\nGET\nSET onlykey\nCONFIG SET maxmemory abc\nEXPIRE k abc\nexit\n' | python3 main.py
```
→ `ERR unknown command 'HELLO'` / `ERR wrong number of arguments for 'GET' command` / `… 'SET' command` / `ERR value is not an integer or out of range` ×2

**8. 자료구조 단독 테스트**
```bash
python3 -m structures.doublyLinkedList   # 3 / ['c','b','a'] / c / a / 0 / None
python3 -m structures.hashMap            # 20 / 32(capacity) / 7 / False / True / None / 19 / 2 20
python3 -m structures.heap               # (1,'a') / (1,'a') / (3,'c') / 1 / [1..9] / None
```

## 실행 예시

```
mini-redis> CONFIG SET maxmemory 30
OK
mini-redis> SET user:1 "Alice"
OK
mini-redis> SET user:2 "Bob"
OK
mini-redis> SET user:3 "Charlie"
OK
mini-redis> GET user:1
(nil)
mini-redis> INFO memory
used_memory:22
maxmemory:30
evicted_keys:1
mini-redis> KEYS
1. "user:2"
2. "user:3"
mini-redis> EXPIRE user:2 3
(integer) 1
mini-redis> TTL user:2
(integer) 3
mini-redis> GET user:2      # 3초 후
(nil)
mini-redis> TTL user:2
(integer) -2
mini-redis> HELLO
(error) ERR unknown command 'HELLO'
```
