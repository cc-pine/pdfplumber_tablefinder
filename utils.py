import itertools
from operator import itemgetter

import numpy as np
from pdfminer.pdftypes import PDFObjRef
from pdfminer.psparser import PSLiteral
from pdfminer.utils import PDFDocEncoding
from .table_filtering_utils import *

DEFAULT_X_TOLERANCE = 3
DEFAULT_Y_TOLERANCE = 3
DEFAULT_X_DENSITY = 7.25
DEFAULT_Y_DENSITY = 13


def cluster_list(xs, tolerance=0):
    if tolerance == 0:
        return [[x] for x in sorted(xs)]
    if len(xs) < 2:
        return [[x] for x in sorted(xs)]
    groups = []
    xs = list(sorted(xs))
    current_group = [xs[0]]
    last = xs[0]
    for x in xs[1:]:
        if x <= (last + tolerance):
            current_group.append(x)
        else:
            groups.append(current_group)
            current_group = [x]
        last = x
    groups.append(current_group)
    return groups


def make_cluster_dict(values, tolerance):
    clusters = cluster_list(set(values), tolerance)

    nested_tuples = [
        [(val, i) for val in value_cluster] for i, value_cluster in enumerate(clusters)
    ]

    cluster_dict = dict(itertools.chain(*nested_tuples))
    return cluster_dict


def cluster_objects(objs, attr, tolerance):
    if isinstance(attr, (str, int)):
        attr_getter = itemgetter(attr)
    else:
        attr_getter = attr
    objs = to_list(objs)
    values = map(attr_getter, objs)
    cluster_dict = make_cluster_dict(values, tolerance)

    get_0, get_1 = itemgetter(0), itemgetter(1)

    cluster_tuples = sorted(
        ((obj, cluster_dict.get(attr_getter(obj))) for obj in objs), key=get_1
    )

    grouped = itertools.groupby(cluster_tuples, key=get_1)

    clusters = [list(map(get_0, v)) for k, v in grouped]

    return clusters


def decode_text(s):
    """
    Decodes a PDFDocEncoding string to Unicode.
    Adds py3 compatibility to pdfminer's version.
    """
    if type(s) == bytes and s.startswith(b"\xfe\xff"):
        return str(s[2:], "utf-16be", "ignore")
    else:
        ords = (ord(c) if type(c) == str else c for c in s)
        return "".join(PDFDocEncoding[o] for o in ords)


def resolve_and_decode(obj):
    """Recursively resolve the metadata values."""
    if hasattr(obj, "resolve"):
        obj = obj.resolve()
    if isinstance(obj, list):
        return list(map(resolve_and_decode, obj))
    elif isinstance(obj, PSLiteral):
        return decode_text(obj.name)
    elif isinstance(obj, (str, bytes)):
        return decode_text(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = resolve_and_decode(v)
        return obj

    return obj


def decode_psl_list(_list):
    return [
        decode_text(value.name) if isinstance(value, PSLiteral) else value
        for value in _list
    ]


def resolve(x):
    if type(x) == PDFObjRef:
        return x.resolve()
    else:
        return x


def get_dict_type(d):
    if type(d) is not dict:
        return None
    t = d.get("Type")
    if type(t) is PSLiteral:
        return decode_text(t.name)
    else:
        return t


def resolve_all(x):
    """
    Recursively resolves the given object and all the internals.
    """
    t = type(x)
    if t == PDFObjRef:
        resolved = x.resolve()

        # Avoid infinite recursion
        if get_dict_type(resolved) == "Page":
            return x

        return resolve_all(resolved)
    elif t in (list, tuple):
        return t(resolve_all(v) for v in x)
    elif t == dict:
        if get_dict_type(x) == "Annot":
            exceptions = ["Parent"]
        else:
            exceptions = []
        return dict((k, v if k in exceptions else resolve_all(v)) for k, v in x.items())
    else:
        return x


def is_dataframe(collection):
    cls = collection.__class__
    name = ".".join([cls.__module__, cls.__name__])
    return name == "pandas.core.frame.DataFrame"


def to_list(collection):
    if is_dataframe(collection):
        return collection.to_dict("records")  # pragma: nocover
    else:
        return list(collection)


def dedupe_chars(chars, tolerance=1):
    """
    Removes duplicate chars ?????those sharing the same text, fontname, size,
    and positioning (within `tolerance`) as other characters in the set.
    """
    key = itemgetter("fontname", "size", "upright", "text")
    pos_key = itemgetter("doctop", "x0")

    def yield_unique_chars(chars):
        sorted_chars = sorted(chars, key=key)
        for grp, grp_chars in itertools.groupby(sorted_chars, key=key):
            for y_cluster in cluster_objects(grp_chars, "doctop", tolerance):
                for x_cluster in cluster_objects(y_cluster, "x0", tolerance):
                    yield sorted(x_cluster, key=pos_key)[0]

    deduped = yield_unique_chars(chars)
    return sorted(deduped, key=chars.index)


def objects_to_rect(objects):
    return {
        "x0": min(map(itemgetter("x0"), objects)),
        "x1": max(map(itemgetter("x1"), objects)),
        "top": min(map(itemgetter("top"), objects)),
        "bottom": max(map(itemgetter("bottom"), objects)),
    }


def objects_to_bbox(objects):
    return (
        min(map(itemgetter("x0"), objects)),
        min(map(itemgetter("top"), objects)),
        max(map(itemgetter("x1"), objects)),
        max(map(itemgetter("bottom"), objects)),
    )


obj_to_bbox = itemgetter("x0", "top", "x1", "bottom")


def bbox_to_rect(bbox):
    return {"x0": bbox[0], "top": bbox[1], "x1": bbox[2], "bottom": bbox[3]}


def merge_bboxes(bboxes):
    """
    Given a set of bounding boxes, return the smallest bounding box that
    contains them all.
    """
    return (
        min(map(itemgetter(0), bboxes)),
        min(map(itemgetter(1), bboxes)),
        max(map(itemgetter(2), bboxes)),
        max(map(itemgetter(3), bboxes)),
    )


DEFAULT_WORD_EXTRACTION_SETTINGS = dict(
    x_tolerance=DEFAULT_X_TOLERANCE,
    y_tolerance=DEFAULT_Y_TOLERANCE,
    keep_blank_chars=False,
    use_text_flow=False,
    horizontal_ltr=True,  # Should words be read left-to-right?
    vertical_ttb=True,  # Should vertical words be read top-to-bottom?
    extra_attrs=[],
)


class WordExtractor:
    def __init__(self, **settings):
        for s, val in settings.items():
            if s not in DEFAULT_WORD_EXTRACTION_SETTINGS:
                raise ValueError(f"{s} is not a valid WordExtractor parameter")

            setattr(self, s, val)

    def merge_chars(self, ordered_chars):
        x0, top, x1, bottom = objects_to_bbox(ordered_chars)
        doctop_adj = ordered_chars[0]["doctop"] - ordered_chars[0]["top"]
        upright = ordered_chars[0]["upright"]

        direction = 1 if (self.horizontal_ltr if upright else self.vertical_ttb) else -1

        word = {
            "text": "".join(map(itemgetter("text"), ordered_chars)),
            "x0": x0,
            "x1": x1,
            "top": top,
            "doctop": top + doctop_adj,
            "bottom": bottom,
            "upright": upright,
            "direction": direction,
        }

        for key in self.extra_attrs:
            word[key] = ordered_chars[0][key]

        return word

    def char_begins_new_word(self, current_chars, current_bbox, next_char):
        upright = current_chars[0]["upright"]
        intraline_tol = self.x_tolerance if upright else self.y_tolerance
        interline_tol = self.y_tolerance if upright else self.x_tolerance

        word_x0, word_top, word_x1, word_bottom = current_bbox

        return (
            (next_char["x0"] > word_x1 + intraline_tol)
            or (next_char["x1"] < word_x0 - intraline_tol)
            or (next_char["top"] > word_bottom + interline_tol)
            or (next_char["bottom"] < word_top - interline_tol)
        )

    def iter_chars_to_words(self, chars):
        current_word = []
        current_bbox = None

        for char in chars:
            if not self.keep_blank_chars and char["text"].isspace():
                if current_word:
                    yield current_word
                    current_word = []
                    current_bbox = None

            elif current_word and self.char_begins_new_word(
                current_word, current_bbox, char
            ):
                yield current_word
                current_word = [char]
                current_bbox = obj_to_bbox(char)

            else:
                current_word.append(char)
                if current_bbox is None:
                    current_bbox = obj_to_bbox(char)
                else:
                    current_bbox = merge_bboxes([current_bbox, obj_to_bbox(char)])

        if current_word:
            yield current_word

    def iter_sort_chars(self, chars):
        def upright_key(x):
            return -int(x["upright"])

        for upright_cluster in cluster_objects(chars, upright_key, 0):
            upright = upright_cluster[0]["upright"]
            cluster_key = "doctop" if upright else "x0"

            # Cluster by line
            subclusters = cluster_objects(
                upright_cluster, cluster_key, self.y_tolerance
            )

            for sc in subclusters:
                # Sort within line
                sort_key = "x0" if upright else "doctop"
                sc = sorted(sc, key=itemgetter(sort_key))

                # Reverse order if necessary
                if not (self.horizontal_ltr if upright else self.vertical_ttb):
                    sc = reversed(sc)

                yield from sc

    def iter_extract(self, chars):
        if not self.use_text_flow:
            chars = self.iter_sort_chars(chars)

        grouping_key = itemgetter("upright", *self.extra_attrs)
        grouped = itertools.groupby(chars, grouping_key)

        for keyvals, char_group in grouped:
            for word_chars in self.iter_chars_to_words(char_group):
                yield self.merge_chars(word_chars)

    def extract(self, chars):
        return list(self.iter_extract(chars))


def extract_words(chars, **kwargs):
    settings = dict(DEFAULT_WORD_EXTRACTION_SETTINGS)
    settings.update(kwargs)
    return WordExtractor(**settings).extract(chars)


def words_to_layout(
    words,
    x_density=DEFAULT_X_DENSITY,
    y_density=DEFAULT_Y_DENSITY,
    x_shift=0,
    y_shift=0,
    y_tolerance=DEFAULT_Y_TOLERANCE,
    presorted=False,
):
    """
    Given a set of word objects generated by `extract_words(...)`, return a
    string that mimics the structural layout of the text on the page(s), using
    the following approach:

    - Sort the words by (doctop, x0) if not already sorted.

    - Calculate the initial doctop for the starting page.

    - Cluster the words by doctop (taking `y_tolerance` into account), and
      iterate through them.

    - For each cluster, calculate the distance between that doctop and the
      initial doctop, in points, minus `y_shift`. Divide that distance by
      `y_density` to calculate the minimum number of newlines that should come
      before this cluster. Append that number of newlines *minus* the number of
      newlines already appended, with a minimum of one.

    - Then for each cluster, iterate through each word in it. Divide each
      word's x0, minus `x_shift`, by `x_density` to calculate the minimum
      number of characters that should come before this cluster.  Append that
      number of spaces *minus* the number of characters and spaces already
      appended, with a minimum of one. Then append the word's text.

    Note: This approach currently works best for horizontal, left-to-right
    text, but will display all words regardless of orientation. There is room
    for improvement in better supporting right-to-left text, as well as
    vertical text.
    """
    rendered = ""
    words_sorted = words if presorted else sorted(words, itemgetter("doctop", "x0"))
    doctop_start = words_sorted[0]["doctop"] - words_sorted[0]["top"]
    for ws in cluster_objects(words_sorted, "doctop", y_tolerance):
        y_dist = (ws[0]["doctop"] - (doctop_start + y_shift)) / y_density
        newlines = rendered.count("\n")
        rendered += "\n" * max(min(1, newlines), round(y_dist) - newlines)
        line = ""
        for word in sorted(ws, key=itemgetter("x0")):
            x_dist = (word["x0"] - x_shift) / x_density
            line += " " * max(min(1, len(line)), round(x_dist) - len(line))
            line += word["text"]
        rendered += line
    return rendered


def collate_line(line_chars, tolerance=DEFAULT_X_TOLERANCE, layout=False):
    coll = ""
    last_x1 = None
    for char in sorted(line_chars, key=itemgetter("x0")):
        if (last_x1 is not None) and (char["x0"] > (last_x1 + tolerance)):
            coll += " "
        last_x1 = char["x1"]
        coll += char["text"]
    return coll


def extract_text(
    chars,
    layout=False,
    x_density=DEFAULT_X_DENSITY,
    y_density=DEFAULT_Y_DENSITY,
    x_shift=0,
    y_shift=0,
    **kwargs,
):
    chars = to_list(chars)
    if len(chars) == 0:
        return ""

    if layout:
        words = extract_words(chars, **kwargs)
        y_tolerance = kwargs.get("y_tolerance", DEFAULT_Y_TOLERANCE)
        return words_to_layout(
            words,
            x_density=x_density,
            y_density=y_density,
            x_shift=x_shift,
            y_shift=y_shift,
            y_tolerance=y_tolerance,
            presorted=True,
        )

    else:
        x_tolerance = kwargs.get("x_tolerance", DEFAULT_X_TOLERANCE)
        y_tolerance = kwargs.get("y_tolerance", DEFAULT_Y_TOLERANCE)

        doctop_clusters = cluster_objects(chars, "doctop", y_tolerance)

        lines = (
            collate_line(line_chars, x_tolerance) for line_chars in doctop_clusters
        )

        return "\n".join(lines)


collate_chars = extract_text


def filter_objects(objs, fn):
    if isinstance(objs, dict):
        return dict((k, filter_objects(v, fn)) for k, v in objs.items())

    initial_type = type(objs)
    objs = to_list(objs)
    filtered = filter(fn, objs)

    return initial_type(filtered)


def get_bbox_overlap(a, b):
    a_left, a_top, a_right, a_bottom = a
    b_left, b_top, b_right, b_bottom = b
    o_left = max(a_left, b_left)
    o_right = min(a_right, b_right)
    o_bottom = min(a_bottom, b_bottom)
    o_top = max(a_top, b_top)
    o_width = o_right - o_left
    o_height = o_bottom - o_top
    if o_height >= 0 and o_width >= 0 and o_height + o_width > 0:
        return (o_left, o_top, o_right, o_bottom)
    else:
        return None


def calculate_area(bbox):
    left, top, right, bottom = bbox
    if left > right or top > bottom:
        raise ValueError(f"{bbox} has a negative width or height.")
    return (right - left) * (bottom - top)


def clip_obj(obj, bbox):

    overlap = get_bbox_overlap(obj_to_bbox(obj), bbox)
    if overlap is None:
        return None

    dims = bbox_to_rect(overlap)
    copy = dict(obj)

    for attr in ["x0", "top", "x1", "bottom"]:
        copy[attr] = dims[attr]

    if dims["top"] != obj["bottom"] or dims["top"] != obj["bottom"]:
        diff = dims["top"] - obj["top"]
        copy["doctop"] = obj["doctop"] + diff

    copy["width"] = copy["x1"] - copy["x0"]
    copy["height"] = copy["bottom"] - copy["top"]

    return copy


def intersects_bbox(objs, bbox):
    """
    Filters objs to only those intersecting the bbox
    """
    initial_type = type(objs)
    objs = to_list(objs)
    matching = [
        obj for obj in objs if get_bbox_overlap(obj_to_bbox(obj), bbox) is not None
    ]
    return initial_type(matching)


def within_bbox(objs, bbox):
    """
    Filters objs to only those fully within the bbox
    """
    if isinstance(objs, dict):
        return dict((k, within_bbox(v, bbox)) for k, v in objs.items())

    initial_type = type(objs)
    objs = to_list(objs)
    matching = [
        obj
        for obj in objs
        if get_bbox_overlap(obj_to_bbox(obj), bbox) == obj_to_bbox(obj)
    ]
    return initial_type(matching)


def crop_to_bbox(objs, bbox):
    """
    Filters objs to only those intersecting the bbox,
    and crops the extent of the objects to the bbox.
    """
    if isinstance(objs, dict):
        return dict((k, crop_to_bbox(v, bbox)) for k, v in objs.items())

    initial_type = type(objs)
    objs = to_list(objs)
    cropped = list(filter(None, (clip_obj(obj, bbox) for obj in objs)))
    return initial_type(cropped)


def move_object(obj, axis, value):
    assert axis in ("h", "v")
    if axis == "h":
        new_items = (
            ("x0", obj["x0"] + value),
            ("x1", obj["x1"] + value),
        )
    if axis == "v":
        new_items = [
            ("top", obj["top"] + value),
            ("bottom", obj["bottom"] + value),
        ]
        if "doctop" in obj:
            new_items += [("doctop", obj["doctop"] + value)]
        if "y0" in obj:
            new_items += [
                ("y0", obj["y0"] - value),
                ("y1", obj["y1"] - value),
            ]
    return obj.__class__(tuple(obj.items()) + tuple(new_items))


def snap_objects(objs, attr, tolerance):
    axis = {"x0": "h", "x1": "h", "top": "v", "bottom": "v"}[attr]
    clusters = cluster_objects(objs, attr, tolerance)
    avgs = [sum(map(itemgetter(attr), objs)) / len(objs) for objs in clusters]
    snapped_clusters = [
        [move_object(obj, axis, avg - obj[attr]) for obj in cluster]
        for cluster, avg in zip(clusters, avgs)
    ]
    return list(itertools.chain(*snapped_clusters))


def resize_object(obj, key, value):
    assert key in ("x0", "x1", "top", "bottom")
    old_value = obj[key]
    diff = value - old_value
    new_items = [
        (key, value),
    ]
    if key == "x0":
        assert value <= obj["x1"]
        new_items.append(("width", obj["x1"] - value))
    elif key == "x1":
        assert value >= obj["x0"]
        new_items.append(("width", value - obj["x0"]))
    elif key == "top":
        assert value <= obj["bottom"]
        new_items.append(("doctop", obj["doctop"] + diff))
        new_items.append(("height", obj["height"] - diff))
        if "y1" in obj:
            new_items.append(("y1", obj["y1"] - diff))
    elif key == "bottom":
        assert value >= obj["top"]
        new_items.append(("height", obj["height"] + diff))
        if "y0" in obj:
            new_items.append(("y0", obj["y0"] - diff))
    return obj.__class__(tuple(obj.items()) + tuple(new_items))


def curve_to_edges(curve):
    point_pairs = zip(curve["points"], curve["points"][1:])
    return [
        {
            "x0": min(p0[0], p1[0]),
            "x1": max(p0[0], p1[0]),
            "top": min(p0[1], p1[1]),
            "doctop": min(p0[1], p1[1]) + (curve["doctop"] - curve["top"]),
            "bottom": max(p0[1], p1[1]),
            "width": abs(p0[0] - p1[0]),
            "height": abs(p0[1] - p1[1]),
            "orientation": "v" if p0[0] == p1[0] else ("h" if p0[1] == p1[1] else None),
        }
        for p0, p1 in point_pairs
    ]


def rect_to_edges(rect):
    top, bottom, left, right = [dict(rect) for x in range(4)]
    top.update(
        {
            "object_type": "rect_edge",
            "height": 0,
            "y0": rect["y1"],
            "bottom": rect["top"],
            "orientation": "h",
        }
    )
    bottom.update(
        {
            "object_type": "rect_edge",
            "height": 0,
            "y1": rect["y0"],
            "top": rect["top"] + rect["height"],
            "doctop": rect["doctop"] + rect["height"],
            "orientation": "h",
        }
    )
    left.update(
        {
            "object_type": "rect_edge",
            "width": 0,
            "x1": rect["x0"],
            "orientation": "v",
        }
    )
    right.update(
        {
            "object_type": "rect_edge",
            "width": 0,
            "x0": rect["x1"],
            "orientation": "v",
        }
    )
    return [top, bottom, left, right]


def line_to_edge(line):
    edge = dict(line)
    edge["orientation"] = "h" if (line["top"] == line["bottom"]) else "v"
    return edge


def obj_to_edges(obj):
    return {
        "line": lambda x: [line_to_edge(x)],
        "rect": rect_to_edges,
        "rect_edge": rect_to_edges,
        "curve": curve_to_edges,
    }[obj["object_type"]](obj)


def filter_edges(edges, orientation=None, edge_type=None, min_length=1):

    if orientation not in ("v", "h", None):
        raise ValueError("Orientation must be 'v' or 'h'")

    def test(e):
        dim = "height" if e["orientation"] == "v" else "width"
        et_correct = e["object_type"] == edge_type if edge_type is not None else True
        orient_correct = orientation is None or e["orientation"] == orientation
        return et_correct and orient_correct and (e[dim] >= min_length)

    edges = filter(test, edges)
    return list(edges)


def get_bbox_from_object(obj):
    return (obj["x0"], obj["top"], obj["x1"], obj["bottom"])


def get_bboxlist_from_objectlist(obj_list):
    return [get_bbox_from_object(obj) for obj in obj_list]

def get_bboxlist_from_tablelist(table_list):
    return [table.bbox for table in table_list]

def get_overlapping_index(overlap_list, get_first=True):
    if get_first:
        return sorted(list(set([x[0] for x in overlap_list])))
    else:
        return sorted(list(set([x[1] for x in overlap_list])))


def get_cell_size(cell: "tuple[float, float, float, float]") -> "tuple[float, float]":
    """
    Get the height and width of the cell.

    Parameters
    ----------
    cell: tuple of list[float, float, float, float]

    Returns
    -------
    height: float
    width: float

    Notes
    -----
    cell???(x0, top, x1, bottom)????????????
    """
    return cell[3] - cell[1],cell[2] - cell[0]


def get_cell_idxs_overlapped_with_chars(table, page):
    page_table_area = crop_page_within_table(page, table)
    cells_bbox = table.cells
    chars_bbox = get_bboxlist_from_objectlist(page_table_area.chars)
    overlap_list = get_overlapped_bboxes_pairs(cells_bbox, chars_bbox)
    cells_with_overlap = get_overlapping_index(overlap_list)
    return cells_with_overlap


def get_min_char_size(page: "pdfplumber.page.Page") -> "tuple[float, float]":
    """
    Get the minimum height / width of character in page.

    Parameters
    ----------
    page: pdfplumber.page.Page or pdfplumber.page.CroppedPage

    Returns
    -------
    min_height: float
    min_width: float
    """
    chars = page.chars
    min_height = page.height
    min_width = page.width
    for char in chars:
        min_height = min(min_height, char["height"])
        min_width = min(min_width, char["width"])
    return min_height, min_width



def get_mode_char_size(
    page: "pdfplumber.page.Page" or "pdfplumber.page.CroppedPage",
) -> "tuple[float, float]":
    """
    Get the height / width of character that appears most in page.

    Parameters
    ----------
    page: pdfplumber.page.Page or pdfplumber.page.CroppedPage

    Returns
    -------
    mode_height: float
    mode_width: float
    """
    chars = page.chars
    height_list = [c["height"] for c in chars]
    width_list = [c["width"] for c in chars]
    height_unique, height_count = np.unique(height_list, return_counts=True)
    width_unique, width_count = np.unique(width_list, return_counts=True)
    mode_height = height_unique[height_count == np.amax(height_count)].min()
    mode_width = width_unique[width_count == np.amax(width_count)].min()
    return mode_height, mode_width


def get_overlapped_bboxes_pairs(bbox_list1, bbox_list2):
    """
    return: list of pair of indexes with overlap
    """
    # bbox: (x1, y1, x2, y2)
    bbox_events = []

    for i, bbox in enumerate(bbox_list1):
        bbox_events.append(("box1", bbox[0], i, 0))
        bbox_events.append(("box1", bbox[2], i, 1))
    for i, bbox in enumerate(bbox_list2):
        bbox_events.append(("box2", bbox[0], i, 0))
        bbox_events.append(("box2", bbox[2], i, 1))
    bbox_events.sort(key=lambda x: (x[1], -1 * x[3]))
    bbox1_sweeping = []
    bbox2_sweeping = []
    overlap_list = []
    # print(bbox_events)

    for event in bbox_events:
        # print("loop:", event)
        bbox_type = event[0]
        bbox_idx = event[2]
        if bbox_type == "box1":
            _, y1, _, y2 = bbox_list1[bbox_idx]
            if event[3] == 0:
                bbox1_sweeping.append((bbox_idx, y1, y2))
                for bbox2 in bbox2_sweeping:
                    bbox2_idx, bbox2_y1, bbox2_y2 = bbox2
                    if bbox2_y1 < y2 and bbox2_y2 > y1:
                        overlap_list.append((bbox_idx, bbox2_idx))
            elif event[3] == 1:
                bbox1_sweeping.remove((bbox_idx, y1, y2))
        else:
            _, y1, _, y2 = bbox_list2[bbox_idx]
            if event[3] == 0:
                bbox2_sweeping.append((bbox_idx, y1, y2))
                for bbox1 in bbox1_sweeping:
                    bbox1_idx, bbox1_y1, bbox1_y2 = bbox1
                    if bbox1_y1 < y2 and bbox1_y2 > y1:
                        overlap_list.append((bbox1_idx, bbox_idx))
            elif event[3] == 1:
                bbox2_sweeping.remove((bbox_idx, y1, y2))
        # print(bbox1_sweeping, bbox2_sweeping)

    assert len(bbox1_sweeping) == 0

    return overlap_list


def naive_get_overlapped_bboxes_pairs(bbox_list1, bbox_list2):
    overlap_list = []
    for i, bbox1 in enumerate(bbox_list1):
        x1_b1, y1_b1, x2_b1, y2_b1 = bbox1
        for j, bbox2 in enumerate(bbox_list2):
            x1_b2, y1_b2, x2_b2, y2_b2 = bbox2
            if (x1_b1 < x2_b2 and x2_b1 > x1_b2) and (y1_b1 < y2_b2 and y2_b1 > y1_b2):
                overlap_list.append((i, j))
    return overlap_list


def get_cell_nums(table):
    """
    return:
        n_row, n_col: The number of cells on table in a row/col direction
    """
    row = set((cell[1], cell[3]) for cell in table.cells)
    col = set((cell[0], cell[2]) for cell in table.cells)

    n_row = len(row)
    n_col = len(col)
    return n_row, n_col


def crop_page_within_table(page, table):
    bbox = table.bbox
    page_x0, page_top, _, _ = page.bbox
    bbox = (
        bbox[0] + page_x0,
        bbox[1] + page_top,
        bbox[2] + page_x0,
        bbox[3] + page_top,
    )
    return page.within_bbox(bbox)


def get_unique_list(seq):
    seen = []
    return [x for x in seq if x not in seen and not seen.append(x)]
