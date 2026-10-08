"""Mini Redis 코어 저장소.

세 자료구조를 조합한다.

    HashMap            key -> _StoreEntry(value, node, expire_at)   : 값 조회 O(1)
    DoublyLinkedList   [최근] ... [오래됨]  각 노드의 data = key     : LRU 순서 O(1)
    MinHeap            (expire_at, key)                             : 가장 이른 만료 O(1) 확인

엔트리가 LRU 노드 참조를 직접 들고 있으므로(`entry.node`),
GET 시 리스트를 순회하지 않고 곧바로 move_to_front 할 수 있다.
반대로 LRU 노드는 data 에 키를 담고 있어, eviction 시 해시맵도 탐색 없이 정리된다.
"""

import math
import time

from structures.doublyLinkedList import DoublyLinkedList
from structures.hashMap import HashMap
from structures.heap import MinHeap

# TTL 미설정을 나타내는 값
NO_EXPIRE = None

# 한 번의 명령에서 능동 만료로 처리할 최대 키 개수 (한 명령이 오래 멈추지 않도록 제한)
ACTIVE_EXPIRE_LIMIT = 20


class OOMError(Exception):
    """단일 엔트리(키+값)가 maxmemory 를 초과해 저장할 수 없을 때."""


class _StoreEntry:
    """해시맵의 값 자리에 저장되는 상자.

    value      : 실제 값 문자열
    node       : LRU 리스트에서 이 키를 담고 있는 Node 참조 (O(1) 이동/삭제용)
    expire_at  : 만료 시각(epoch 초). TTL 이 없으면 None
    """

    def __init__(self, value, node, expire_at=NO_EXPIRE):
        self.value = value
        self.node = node
        self.expire_at = expire_at


class MiniRedis:
    """String 명령어 + LRU eviction + TTL 만료를 처리하는 저장소."""

    def __init__(self):
        self._map = HashMap()
        self._lru = DoublyLinkedList()
        self._expires = MinHeap()

        self.used_memory = 0
        self.maxmemory = 0  # 0 = 무제한
        self.evicted_keys = 0

    # ------------------------------------------------------------------
    # 메모리 계산
    # ------------------------------------------------------------------

    def _entry_size(self, key, value):
        """used_memory 산정 공식: len(utf8(key)) + len(utf8(value)).

        노드/포인터/버킷 등 자료구조 오버헤드는 제외한다.
        """
        return len(key.encode("utf-8")) + len(value.encode("utf-8"))

    # ------------------------------------------------------------------
    # 만료 처리
    # ------------------------------------------------------------------

    def _is_expired(self, entry, now=None):
        if entry.expire_at is NO_EXPIRE:
            return False
        if now is None:
            now = time.time()

        return entry.expire_at <= now

    def _purge(self, key, entry):
        """데이터 / LRU / used_memory 에서 키를 완전히 제거한다.

        TTL 힙 항목은 남겨두고 pop 시점에 stale 로 판정해 버린다(lazy deletion).
        힙에서 임의 항목을 지우려면 O(n) 탐색이 필요하기 때문이다.
        """
        self._map.remove(key)
        self._lru.remove_node(entry.node)
        self.used_memory -= self._entry_size(key, entry.value)

    def _expire_if_needed(self, key):
        """키가 만료됐으면 삭제한다. 삭제했으면 True.

        모든 키 기반 명령이 실행 전에 호출한다(lazy expiration).
        만료 삭제는 '사용'이 아니므로 LRU 를 갱신하지 않는다.
        """
        entry = self._map.get(key)
        if entry is None:
            return False
        if not self._is_expired(entry):
            return False

        self._purge(key, entry)

        return True

    def active_expire(self):
        """힙 루트부터 확인하며 이미 만료된 키들을 걷어낸다.

        힙 덕분에 '가장 이른 만료'를 O(1)에 확인할 수 있으므로,
        아직 만료되지 않았으면 즉시 멈춘다(뒤쪽은 볼 필요가 없다).
        """
        now = time.time()
        processed = 0

        while processed < ACTIVE_EXPIRE_LIMIT:
            top = self._expires.peek()
            if top is None:
                break

            expire_at, key = top
            if expire_at > now:
                break

            self._expires.pop()
            processed += 1

            entry = self._map.get(key)
            if entry is None:
                continue  # 이미 지워진 키 - stale 항목
            if entry.expire_at != expire_at:
                continue  # TTL 이 갱신·초기화됨 - stale 항목

            self._purge(key, entry)

    def _live_entry(self, key):
        """만료 검사를 거친 뒤 살아 있는 엔트리를 반환한다. 없으면 None."""
        if self._expire_if_needed(key):
            return None

        return self._map.get(key)

    # ------------------------------------------------------------------
    # LRU eviction
    # ------------------------------------------------------------------

    def _evict_until_fit(self):
        """used_memory 가 maxmemory 이하가 될 때까지 LRU 부터 제거한다."""
        if self.maxmemory <= 0:
            return

        while self.used_memory > self.maxmemory and not self._lru.is_empty():
            key = self._lru.remove_back()  # 가장 오래 사용되지 않은 키
            entry = self._map.get(key)
            if entry is None:
                continue

            self._map.remove(key)
            self.used_memory -= self._entry_size(key, entry.value)
            self.evicted_keys += 1

    # ------------------------------------------------------------------
    # String 명령어
    # ------------------------------------------------------------------

    def set(self, key, value):
        """키에 값을 저장한다.

        - 덮어쓰기인 경우 기존 TTL 을 초기화한다
        - 단일 엔트리가 maxmemory 를 넘으면 저장하지 않고 OOMError
        - 저장 후 초과분은 LRU 부터 제거한다
        """
        size = self._entry_size(key, value)
        if self.maxmemory > 0 and size > self.maxmemory:
            raise OOMError()

        entry = self._live_entry(key)

        if entry is not None:
            # 덮어쓰기: 값 교체 + TTL 초기화 + 메모리 증분 갱신
            self.used_memory -= self._entry_size(key, entry.value)
            entry.value = value
            entry.expire_at = NO_EXPIRE
            self.used_memory += size
            self._lru.move_to_front(entry.node)
        else:
            node = self._lru.insert_front(key)
            self._map.put(key, _StoreEntry(value, node))
            self.used_memory += size

        self._evict_until_fit()

    def get(self, key):
        """값을 반환한다. 없거나 만료됐으면 None.

        조회에 성공한 경우에만 LRU 를 갱신한다.
        """
        entry = self._live_entry(key)
        if entry is None:
            return None

        self._lru.move_to_front(entry.node)

        return entry.value

    def delete(self, key):
        """키를 삭제한다. 삭제했으면 1, 없었으면 0.

        데이터 / LRU / used_memory 를 함께 정리한다.
        """
        entry = self._live_entry(key)
        if entry is None:
            return 0

        self._purge(key, entry)

        return 1

    def exists(self, key):
        """존재하면 1, 없으면 0."""
        return 1 if self._live_entry(key) is not None else 0

    def dbsize(self):
        """살아 있는 키 개수."""
        self.active_expire()

        return self._map.size()

    def keys(self):
        """살아 있는 키 목록. 순서는 보장하지 않는다."""
        self.active_expire()

        now = time.time()
        result = []
        for key in self._map.keys():
            entry = self._map.get(key)
            if entry is not None and not self._is_expired(entry, now):
                result.append(key)

        return result

    # ------------------------------------------------------------------
    # TTL 명령어
    # ------------------------------------------------------------------

    def expire(self, key, seconds):
        """만료 시간을 초 단위로 설정한다.

        없는 키면 0, 설정했으면 1.
        seconds 가 0 이하면 즉시 만료로 처리한다(삭제 후 1).
        """
        entry = self._live_entry(key)
        if entry is None:
            return 0

        if seconds <= 0:
            self._purge(key, entry)
            return 1

        expire_at = time.time() + seconds
        entry.expire_at = expire_at
        self._expires.push((expire_at, key))

        return 1

    def ttl(self, key):
        """남은 만료 시간(초).

        없는 키면 -2, TTL 미설정이면 -1, 설정돼 있으면 남은 초.
        """
        entry = self._live_entry(key)
        if entry is None:
            return -2
        if entry.expire_at is NO_EXPIRE:
            return -1

        remaining = entry.expire_at - time.time()

        return max(0, int(math.ceil(remaining)))

    # ------------------------------------------------------------------
    # 메모리 관리 명령어
    # ------------------------------------------------------------------

    def config_set_maxmemory(self, value):
        """maxmemory 를 설정한다(바이트). 0 은 무제한.

        설정 직후 초과 상태라면 즉시 LRU 제거를 수행한다.
        """
        self.maxmemory = value
        self._evict_until_fit()

    def info_memory(self):
        """(used_memory, maxmemory, evicted_keys) 를 반환한다."""
        self.active_expire()

        return self.used_memory, self.maxmemory, self.evicted_keys


if __name__ == "__main__":
    r = MiniRedis()
    r.set("a", "1")
    r.set("b", "2")
    print(r.get("a"))  # 1
    print(r.exists("b"))  # 1
    print(r.delete("a"))  # 1
    print(r.delete("a"))  # 0
    print(r.dbsize())  # 1
    print(r.keys())  # ['b']
