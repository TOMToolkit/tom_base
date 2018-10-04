class RiseSetPair:
    def __init__(self, rise_val, set_val):
        self.left_child = None
        self.right_child = None
        self.rise = rise_val
        self.set = set_val

# Binary search tree to store rise set values
class RiseSetTree:
    def __init__(self):
        self.root = None
        self.size = 0

    def len(self):
        return self.size

    def add_rise_set_pair(self, node):
        if self.root is None:
            self.root = node
        else:
            self._add_rise_set_pair(node, self.root)
        self.size += 1

    def _add_rise_set_pair(self, new_node, curr_node):
        if curr_node.rise > new_node.rise:
            if curr_node.left_child is None:
                curr_node.left_child = new_node
            else:
                self._add_rise_set_pair(curr_node.left_child, new_node)
        else:
            if curr_node.right_child is None:
                curr_node.right_child = new_node
            else:
                self._add_rise_set_pair(curr_node.right_child, new_node)

    def get_last_rise(self, rise_val):
        if not self.root:
            return None
        else:
            return self._get_last_rise(rise_val, self.root)

    def _get_last_rise(self, rise_val, node):
        if not node:
            return None
        elif rise_val == node.rise or (rise_val > node.rise and (node.right_child is None or rise_val < node.right_child.rise)):
            return node
        elif rise_val < node.rise:
            return self._get_last_rise(rise_val, node.left_child)
        else:
            return self._get_last_rise(rise_val, node.right_child)

    def get_next_rise(self, rise_val):
        if not self.root:
            return None
        else:
            return self._get_next_rise(rise_val, self.root)

    def _get_next_rise(self, rise_val, node):
        if not node:
            return None
        elif rise_val == node.rise or (rise_val < node.rise and (node.right_child is None or rise_val > node.right_child.rise)):
            return node
        elif rise_val > node.rise:
            return self._get_next_rise(rise_val, node.left_child)
        else:
            return self._get_next_rise(rise_val, node.right_child)

