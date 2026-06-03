"""Pure-Python Squarified Treemap algorithm.

Reference
---------
Bruls, M., Huijsen, K., & van Wijk, J. J. (2000).
"Squarified Treemaps". In Proceedings of the Joint Eurographics and
IEEE TCVG Symposium on Visualization (VisSym '00), pp. 33-42.
https://vanwijk.win.tue.nl/stm.pdf

This implementation follows the spirit of Algorithm 4 of the paper
(``Squarify``) — the iterative look-ahead variant that grows a row
while the worst aspect ratio monotonically improves and then recurses
on the remaining area.  The same approach is used by the popular
``squarify`` PyPI package.  The implementation is matplotlib-free for
the layout itself; a thin ``plot()`` helper is provided so the existing
``TreemapView`` (which historically depended on the third-party
``squarify`` PyPI package) can keep working without any third-party
dependency for the layout.
"""
from __future__ import annotations

from typing import Iterable, List, NamedTuple, Optional, Sequence, Tuple

try:
    import matplotlib
    import matplotlib.patches as _patches
    import matplotlib.pyplot as _plt
    _MPL_AVAILABLE = True
except Exception:  # pragma: no cover - matplotlib is part of the runtime
    _MPL_AVAILABLE = False


Rect = NamedTuple('Rect', [('label', str), ('x', float), ('y', float), ('w', float), ('h', float)])


def _worst_ratio(row_areas: Sequence[float], width: float, height: float) -> float:
    """Worst aspect ratio when laying out ``row_areas`` inside a
    ``width x height`` rectangle.

    The layout direction is dictated by the aspect of the enclosing
    rectangle: if ``width >= height`` every rectangle in the row is
    forced to share the same *width* (= ``sum(areas) / height``) and
    each rectangle's *height* is derived from its area.  Otherwise the
    rectangles share the same *height* (= ``sum(areas) / width``).
    This matches the ``layoutrow`` / ``layoutcol`` convention used by
    the reference implementation in the ``squarify`` PyPI package.
    """
    if not row_areas or width <= 0 or height <= 0:
        return float('inf')
    positives = [a for a in row_areas if a > 0]
    if not positives:
        return float('inf')
    s = sum(positives)
    if s <= 0:
        return float('inf')
    horizontal = width >= height
    if horizontal:
        col_w = s / height  # all items share this width
        worst = 0.0
        for a in positives:
            h = a / col_w
            ar = max(col_w / h, h / col_w)
            if ar > worst:
                worst = ar
        return worst
    else:
        row_h = s / width  # all items share this height
        worst = 0.0
        for a in positives:
            w = a / row_h
            ar = max(w / row_h, row_h / w)
            if ar > worst:
                worst = ar
        return worst


def _layout_items(
    row: Sequence[Tuple[str, float]],
    x: float,
    y: float,
    width: float,
    height: float,
) -> Tuple[List[Rect], Tuple[float, float, float, float]]:
    """Place ``row`` in a strip aligned with the shorter side and
    return both the placed rectangles and the bounding box of the
    remaining area as ``(new_x, new_y, new_w, new_h)``.

    When ``width >= height`` the items are stacked along the y-axis
    (each item spans the full width).  When ``width < height`` the
    items are laid out along the x-axis (each item spans the full
    height).
    """
    rects: List[Rect] = []
    positives = [(label, area) for label, area in row if area > 0]
    if not positives or width <= 0 or height <= 0:
        return rects, (x, y, width, height)
    s = sum(a for _, a in positives)
    if s <= 0:
        return rects, (x, y, width, height)
    horizontal = width >= height
    if horizontal:
        col_w = s / height
        cur_y = y
        for label, area in positives:
            h = area / col_w
            rects.append(Rect(label, float(x), float(cur_y), float(col_w), float(h)))
            cur_y += h
        new_x = x + col_w
        new_y = y
        new_w = max(0.0, width - col_w)
        new_h = height
    else:
        row_h = s / width
        cur_x = x
        for label, area in positives:
            w = area / row_h
            rects.append(Rect(label, float(cur_x), float(y), float(w), float(row_h)))
            cur_x += w
        new_x = x
        new_y = y + row_h
        new_w = width
        new_h = max(0.0, height - row_h)
    return rects, (float(new_x), float(new_y), float(new_w), float(new_h))


def _squarify_recursive(
    items: Sequence[Tuple[str, float]],
    x: float,
    y: float,
    width: float,
    height: float,
) -> List[Rect]:
    """Recursive squarified layout for ``items`` inside ``(x, y, width, height)``.

    ``items`` must be sorted by area descending and already normalised
    so that ``sum(area) == width * height``.
    """
    if not items:
        return []
    if width <= 0 or height <= 0:
        return []
    if len(items) == 1:
        label, _ = items[0]
        return [Rect(label, float(x), float(y), float(width), float(height))]

    areas = [a for _, a in items]
    # Greedy look-ahead: grow the current row while adding another
    # item does not strictly *worsen* the worst aspect ratio.
    # Matches the ``>=`` tie-breaking used by the third-party
    # ``squarify`` package.
    i = 1
    while i < len(areas):
        prev = _worst_ratio(areas[:i], width, height)
        curr = _worst_ratio(areas[: i + 1], width, height)
        if curr > prev:
            break
        i += 1

    current = items[:i]
    remaining = items[i:]

    placed, (nx, ny, nw, nh) = _layout_items(current, x, y, width, height)
    if remaining and nw > 0 and nh > 0:
        placed.extend(_squarify_recursive(remaining, nx, ny, nw, nh))
    return placed


def squarify(
    items: List[Tuple[str, float]],
    width: int,
    height: int,
) -> List[Rect]:
    """Compute a squarified treemap layout.

    Parameters
    ----------
    items:
        ``(label, area)`` pairs.  ``area`` must be > 0.  Items with
        non-positive area are dropped.  The list does not need to be
        sorted; ``squarify`` sorts by area descending as required by
        Algorithm 1 of the paper.
    width, height:
        The dimensions of the enclosing rectangle in user units (the
        unit is opaque to the algorithm; in the GUI it is pixels).

    Returns
    -------
    list[Rect]
        ``Rect(label, x, y, w, h)`` entries.  ``(0, 0)`` is the top-left
        corner.  ``x`` grows to the right and ``y`` grows downward.  An
        empty input yields an empty list.
    """
    if not items:
        return []
    if width <= 0 or height <= 0:
        return []

    positives = [(label, float(area)) for label, area in items if area is not None and float(area) > 0]
    if not positives:
        return []

    total = sum(a for _, a in positives)
    if total <= 0:
        return []

    fw, fh = float(width), float(height)
    scale = (fw * fh) / total
    normalised = [(label, a * scale) for label, a in positives]
    normalised.sort(key=lambda kv: -kv[1])

    return _squarify_recursive(normalised, 0.0, 0.0, fw, fh)


# ---------------------------------------------------------------------------
# Optional matplotlib helper — kept so ``TreemapView`` (and any other
# caller that previously relied on the third-party ``squarify.plot`` API)
# can keep working.  Plotting is a thin convenience on top of the pure
# layout in :func:`squarify`; the algorithm itself is matplotlib-free.
# ---------------------------------------------------------------------------

def plot(
    sizes: Iterable[float],
    label: Optional[Iterable[str]] = None,
    alpha: float = 0.8,
    ax=None,
    color=None,
    edgecolor: str = 'white',
    linewidth: float = 2.0,
    text_kwargs: Optional[dict] = None,
    pad_ratio: float = 0.02,
):
    """Draw a squarified treemap on a matplotlib ``Axes``.

    Mirrors the small subset of the third-party ``squarify.plot`` API
    that the existing ``TreemapView`` relies on.

    Parameters
    ----------
    sizes:
        Iterable of non-negative areas.
    label:
        Optional iterable of string labels, one per size.  If ``None``
        the integer index is used.
    alpha:
        Rectangle face alpha.
    ax:
        Target ``Axes``.  Defaults to ``plt.gca()``.
    color:
        Optional colour (anything matplotlib accepts) used for every
        rectangle.  When ``None`` a Spectral colormap is used.
    edgecolor, linewidth:
        Rectangle border styling.
    text_kwargs:
        Extra keyword arguments forwarded to ``Axes.text``.
    pad_ratio:
        Inner padding (as a fraction of the smaller side) applied to
        every rectangle so that adjacent blocks are visually
        separated.
    """
    if not _MPL_AVAILABLE:  # pragma: no cover - import-time check
        raise RuntimeError("matplotlib is required for squarify.plot()")

    if ax is None:
        ax = _plt.gca()

    sizes_list = [float(s) for s in sizes if s is not None and float(s) > 0]
    if not sizes_list:
        ax.set_axis_off()
        return ax

    if label is None:
        label_list = [str(i) for i in range(len(sizes_list))]
    else:
        label_iter = list(label)
        if len(label_iter) < len(sizes_list):
            label_iter = label_iter + [str(i) for i in range(len(label_iter), len(sizes_list))]
        label_list = label_iter[: len(sizes_list)]

    # Use a normalised 100x100 space — the exact unit does not matter
    # because matplotlib rescales the patches to fill the axes box.
    width, height = 100, 100
    rects = squarify(list(zip(label_list, sizes_list)), width, height)
    n = len(rects)

    pad = pad_ratio * min(width, height)
    cmap = _plt.get_cmap('Spectral') if color is None else None
    text_kwargs = dict(text_kwargs or {})
    text_kwargs.setdefault('ha', 'center')
    text_kwargs.setdefault('va', 'center')

    for i, r in enumerate(rects):
        if color is not None:
            face = color
        else:
            face = cmap(i / max(1, n - 1)) if n > 1 else cmap(0.5)
        patch = _patches.Rectangle(
            (r.x + pad, r.y + pad),
            max(0.0, r.w - 2 * pad),
            max(0.0, r.h - 2 * pad),
            facecolor=face,
            edgecolor=edgecolor,
            alpha=alpha,
            linewidth=linewidth,
        )
        ax.add_patch(patch)
        if r.w > 6 and r.h > 6:
            rx = r.x + r.w / 2
            ry = r.y + r.h / 2
            font_size = max(6, min(14, int(min(r.w, r.h) / 6)))
            text_kwargs.setdefault('fontsize', font_size)
            ax.text(rx, ry, r.label, **text_kwargs)

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)  # invert y so origin is top-left
    ax.set_aspect('auto')
    ax.set_axis_off()
    return ax


__all__ = ['Rect', 'squarify', 'plot']
