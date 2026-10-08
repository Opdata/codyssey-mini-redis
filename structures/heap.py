"""최소 힙 (Min Heap).

배열(파이썬 list)로 완전 이진 트리를 표현한다.
인덱스 i 를 기준으로

    부모   = (i - 1) // 2
    왼자식 = 2 * i + 1
    오자식 = 2 * i + 2

TTL 관리에 쓴다. 요소는 `(expire_at, key)` 튜플이며,
튜플 비교는 앞 원소부터 이뤄지므로 만료 시각이 가장 이른 항목이 루트에 온다.
따라서 "가장 먼저 만료될 키"를 O(1)에 확인(peek)할 수 있다.
"""


class MinHeap:
    """배열 기반 최소 힙.

    push / pop 은 트리 높이만큼만 이동하므로 O(log n),
    peek / size 는 O(1).
    """

    def __init__(self):
        self._items = []

    @property
    def size(self):
        """저장된 요소 개수. O(1)"""
        return len(self._items)

    def is_empty(self):
        return len(self._items) == 0

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _swap(self, i, j):
        self._items[i], self._items[j] = self._items[j], self._items[i]

    def _heapify_up(self, index):
        """index 의 요소를 부모와 비교하며 위로 올린다. O(log n)

        새 요소를 배열 끝에 넣은 뒤, 부모보다 작으면 계속 교환한다.
        """
        while index > 0:
            parent = (index - 1) // 2
            if self._items[index] >= self._items[parent]:
                break
            self._swap(index, parent)
            index = parent

    def _heapify_down(self, index):
        """index 의 요소를 자식과 비교하며 아래로 내린다. O(log n)

        루트를 꺼낸 뒤 마지막 요소를 루트로 올렸을 때 힙 성질을 복구한다.
        두 자식 중 더 작은 쪽과 비교·교환한다.
        """
        n = len(self._items)
        while True:
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index

            if left < n and self._items[left] < self._items[smallest]:
                smallest = left
            if right < n and self._items[right] < self._items[smallest]:
                smallest = right

            if smallest == index:
                break

            self._swap(index, smallest)
            index = smallest

    # ------------------------------------------------------------------
    # 공개 메서드
    # ------------------------------------------------------------------

    def push(self, item):
        """요소를 추가한다. O(log n)"""
        self._items.append(item)
        self._heapify_up(len(self._items) - 1)

    def pop(self):
        """가장 작은 요소를 꺼내 반환한다. 비어 있으면 None. O(log n)"""
        if not self._items:
            return None

        smallest = self._items[0]
        last = self._items.pop()

        if self._items:
            self._items[0] = last
            self._heapify_down(0)

        return smallest

    def peek(self):
        """가장 작은 요소를 꺼내지 않고 확인한다. 비어 있으면 None. O(1)"""
        if not self._items:
            return None

        return self._items[0]


if __name__ == "__main__":
    h = MinHeap()
    for x in [(5, "e"), (1, "a"), (3, "c")]:
        h.push(x)
    print(h.peek())  # (1, 'a')
    print(h.pop())  # (1, 'a')
    print(h.pop())  # (3, 'c')
    print(h.size)  # 1

    h2 = MinHeap()
    for x in [9, 4, 7, 1, 8, 2, 6, 3, 5]:
        h2.push(x)
    order = []
    while not h2.is_empty():
        order.append(h2.pop())
    print(order)  # 1..9 정렬
    print(h2.pop())  # None
