"""해시맵 (체이닝 방식).

내장 dict / set / collections 를 쓰지 않고 직접 구현한다.
버킷 테이블만 "고정 길이 배열 + 인덱스 접근" 용도로 파이썬 list 를 쓴다.

    버킷 배열 (list, 길이 capacity)
      [0] -> 체인: DoublyLinkedList( _Entry, _Entry, ... )
      [1] -> 체인: DoublyLinkedList()
      ...

각 버킷은 이중 연결 리스트(체인)이며, 충돌한 키들이 같은 체인에 담긴다.
"""

from structures.doublyLinkedList import DoublyLinkedList

INITIAL_CAPACITY = 8
MAX_LOAD_FACTOR = 0.75


class _Entry:
    """체인 노드의 data 에 담기는 (키, 값) 쌍.

    버킷 번호만으로는 어느 키인지 구분할 수 없으므로(충돌 가능),
    키를 함께 저장해 두고 체인 안에서 키 비교로 최종 확인한다.
    """

    def __init__(self, key, value):
        self.key = key
        self.value = value


class HashMap:
    """체이닝으로 충돌을 해결하는 해시맵.

    평균 O(1), 최악 O(n) (모든 키가 한 버킷에 몰린 경우).
    로드 팩터가 0.75 를 넘으면 capacity 를 2배로 늘리고 전체를 재해싱한다.
    """

    def __init__(self, capacity=INITIAL_CAPACITY):
        self.capacity = capacity
        self._size = 0
        self._buckets = self._new_buckets(capacity)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _new_buckets(self, capacity):
        """길이 capacity 의 버킷 배열을 만들고 각 칸에 빈 체인을 넣는다."""
        buckets = [None] * capacity
        for i in range(capacity):
            buckets[i] = DoublyLinkedList()

        return buckets

    def _hash(self, key):
        """djb2 계열 해시 함수 (직접 구현).

        h = h * 33 + ord(ch) 를 누적하며 32비트로 자른다.
        같은 키는 항상 같은 값을 돌려줘야 저장·조회가 같은 버킷으로 간다.
        """
        h = 5381
        for ch in str(key):
            h = (h * 33 + ord(ch)) & 0xFFFFFFFF

        return h

    def _index(self, key):
        """키가 들어갈 버킷 번호. 해시값을 capacity 로 나눈 나머지."""
        return self._hash(key) % self.capacity

    def _find_node(self, key):
        """키가 속한 체인에서 해당 노드를 찾는다. 없으면 None.

        체인 길이만큼 키를 비교한다. 로드 팩터를 0.75 이하로 유지하므로
        체인은 평균적으로 매우 짧다.
        """
        chain = self._buckets[self._index(key)]
        cur = chain.head.next
        while cur is not chain.tail:
            if cur.data.key == key:
                return cur
            cur = cur.next

        return None

    def _resize(self):
        """capacity 를 2배로 늘리고 모든 엔트리를 다시 배치한다(재해싱). O(n)

        capacity 가 바뀌면 `해시값 % capacity` 결과가 달라지므로
        기존 엔트리를 그대로 두면 조회할 때 찾지 못한다.
        """
        old_buckets = self._buckets

        self.capacity = self.capacity * 2
        self._buckets = self._new_buckets(self.capacity)

        for chain in old_buckets:
            cur = chain.head.next
            while cur is not chain.tail:
                entry = cur.data
                new_chain = self._buckets[self._index(entry.key)]
                new_chain.insert_back(entry)
                cur = cur.next

    # ------------------------------------------------------------------
    # 공개 메서드
    # ------------------------------------------------------------------

    def put(self, key, value):
        """키에 값을 저장한다. 이미 있으면 값만 덮어쓴다. 평균 O(1)"""
        node = self._find_node(key)
        if node is not None:
            node.data.value = value
            return

        chain = self._buckets[self._index(key)]
        chain.insert_back(_Entry(key, value))
        self._size += 1

        if self.load_factor() > MAX_LOAD_FACTOR:
            self._resize()

    def get(self, key):
        """키에 해당하는 값을 반환한다. 없으면 None. 평균 O(1)"""
        node = self._find_node(key)
        if node is None:
            return None

        return node.data.value

    def remove(self, key):
        """키를 삭제한다. 삭제했으면 True, 없었으면 False. 평균 O(1)"""
        node = self._find_node(key)
        if node is None:
            return False

        chain = self._buckets[self._index(key)]
        chain.remove_node(node)
        self._size -= 1

        return True

    def contains(self, key):
        """키가 존재하면 True. 평균 O(1)"""
        return self._find_node(key) is not None

    def keys(self):
        """저장된 모든 키를 list 로 반환한다. 순서는 보장하지 않는다. O(n + capacity)"""
        result = []
        for chain in self._buckets:
            cur = chain.head.next
            while cur is not chain.tail:
                result.append(cur.data.key)
                cur = cur.next

        return result

    def size(self):
        """저장된 키 개수. O(1)"""
        return self._size

    def load_factor(self):
        """size / capacity. 버킷 하나당 평균 엔트리 수."""
        return self._size / self.capacity


if __name__ == "__main__":
    m = HashMap()
    for i in range(20):
        m.put("k%d" % i, i)
    print(m.size())  # 20
    print(m.capacity)  # 32
    print(m.get("k7"))  # 7
    print(m.contains("k99"))  # False
    print(m.remove("k7"))  # True
    print(m.get("k7"))  # None
    print(len(m.keys()))  # 19

    m.put("dup", 1)
    m.put("dup", 2)
    print(m.get("dup"), m.size())  # 2 20 (덮어쓰기는 size 를 늘리지 않는다)
