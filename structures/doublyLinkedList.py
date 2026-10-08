"""이중 연결 리스트 (Doubly Linked List).

두 곳에서 재사용한다.
  1) LRU 사용 순서 관리 (store.py) - data 에 키 문자열을 담는다.
  2) 해시맵 버킷의 체인 (hashMap.py) - data 에 (key, value) 엔트리를 담는다.

head / tail 센티넬 노드를 두어 "빈 리스트 / 첫 노드 / 마지막 노드" 분기를 없앴다.
모든 삽입·삭제·이동은 탐색 없이 노드 참조만으로 처리하므로 O(1)이다.
"""


class Node:
    """이중 연결 리스트의 노드.

    prev 는 머리(head) 쪽 이웃, next 는 꼬리(tail) 쪽 이웃을 가리킨다.
    양쪽 이웃의 참조를 모두 들고 있으므로, 이 노드 하나만 알면
    리스트를 순회하지 않고 제거·이동할 수 있다.
    """

    def __init__(self, data=None):
        self.data = data
        self.prev = None
        self.next = None


class DoublyLinkedList:
    """센티넬 노드를 사용하는 이중 연결 리스트.

        head <-> (데이터 노드들) <-> tail
        (최근)                      (오래됨)

    센티넬 자체는 size 에 포함하지 않는다.
    """

    def __init__(self):
        self.head = Node()
        self.tail = Node()
        self.size = 0

        self.head.next = self.tail
        self.tail.prev = self.head

    def is_empty(self):
        """데이터 노드가 하나도 없으면 True."""
        return self.size == 0

    # ------------------------------------------------------------------
    # 내부 헬퍼 - 연결만 바꾸고 size 는 건드리지 않는다.
    # size 조정은 호출하는 쪽이 담당한다 (move_to_front 는 개수가 변하지 않으므로).
    # ------------------------------------------------------------------

    def _link_after(self, anchor, node):
        """anchor 바로 뒤에 node 를 끼워 넣는다. O(1)"""
        node.prev = anchor
        node.next = anchor.next
        anchor.next = node
        node.next.prev = node

    def _unlink(self, node):
        """node 를 연결에서 떼어낸다. 양옆 이웃을 서로 직접 잇는다. O(1)"""
        node.next.prev = node.prev
        node.prev.next = node.next
        node.next = None
        node.prev = None

    # ------------------------------------------------------------------
    # 삽입 - 생성된 Node 를 반환한다.
    # 호출자가 이 참조를 보관해 두면 이후 O(1) 이동/삭제가 가능하다.
    # ------------------------------------------------------------------

    def insert_front(self, data):
        """맨 앞(가장 최근 위치)에 삽입하고 Node 를 반환한다. O(1)"""
        node = Node(data)
        self._link_after(self.head, node)
        self.size += 1

        return node

    def insert_back(self, data):
        """맨 뒤(가장 오래된 위치)에 삽입하고 Node 를 반환한다. O(1)"""
        node = Node(data)
        self._link_after(self.tail.prev, node)
        self.size += 1

        return node

    # ------------------------------------------------------------------
    # 삭제 - 떼어낸 노드의 data 를 반환한다.
    # ------------------------------------------------------------------

    def remove_node(self, node):
        """주어진 노드를 제거하고 data 를 반환한다. 탐색이 없으므로 O(1)."""
        self._unlink(node)
        self.size -= 1

        return node.data

    def remove_front(self):
        """맨 앞 노드를 제거하고 data 를 반환한다. 비어 있으면 None. O(1)"""
        if self.is_empty():
            return None

        return self.remove_node(self.head.next)

    def remove_back(self):
        """맨 뒤 노드를 제거하고 data 를 반환한다. 비어 있으면 None. O(1)

        LRU eviction 에서 '가장 오래 사용되지 않은 항목'을 꺼낼 때 쓴다.
        """
        if self.is_empty():
            return None

        return self.remove_node(self.tail.prev)

    # ------------------------------------------------------------------
    # 이동
    # ------------------------------------------------------------------

    def move_to_front(self, node):
        """이미 리스트에 있는 노드를 맨 앞으로 옮긴다. O(1)

        새 Node 를 만들지 않고 연결만 바꾼다.
        (해시맵 엔트리가 이 노드 참조를 들고 있으므로 객체를 유지해야 한다.)
        개수가 변하지 않으므로 size 는 건드리지 않는다.
        """
        if self.head.next is node:
            return

        self._unlink(node)
        self._link_after(self.head, node)

    # ------------------------------------------------------------------
    # 조회 / 디버깅
    # ------------------------------------------------------------------

    def to_list(self):
        """앞에서 뒤 순서로 data 를 모아 반환한다. 디버깅·검증용. O(n)"""
        result = []
        cur = self.head.next
        while cur is not self.tail:
            result.append(cur.data)
            cur = cur.next

        return result


if __name__ == "__main__":
    l = DoublyLinkedList()
    a = l.insert_front("a")
    b = l.insert_front("b")
    c = l.insert_back("c")
    print(l.size)  # 3
    l.move_to_front(c)
    print(l.to_list())  # ['c', 'b', 'a']
    print(l.remove_front())  # c
    print(l.remove_back())  # a
    l.remove_node(b)
    print(l.size)  # 0
    print(l.remove_front())  # None (빈 리스트)
