"""
developing
"""


import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont


class COLORS(object):
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    TRANSPARENT = (0, 0, 0, 0)


DEFAULT_RESOLUTION = 72
DEFAULT_FILL = COLORS.BLUE + (50,)
DEFAULT_STROKE = DEFAULT_STROKE = COLORS.RED + (200,)


def visualize_rectangular(
    page,
    bboxs,
    fill=DEFAULT_FILL,
    stroke=DEFAULT_STROKE,
    stroke_width=1,
    fontsize=15,
    resolution=150,
):
    res_ratio = resolution / DEFAULT_RESOLUTION
    im = page.to_image(resolution=resolution).original
    annotated = PIL.Image.new(im.mode, im.size)
    annotated.paste(im)

    try:
        arial_font = PIL.ImageFont.truetype("arial.ttf", fontsize)
    except:
        arial_font = PIL.ImageFont.truetype("Arial Unicode.ttf", fontsize)

    draw = PIL.ImageDraw.Draw(annotated, "RGBA")
    for i, bbox in enumerate(bboxs):
        x0, top, x1, bottom = get_coords_for_plot_rect(bbox, resolution, stroke_width)
        draw_rect(draw, x0, top, x1, bottom, fill, stroke, stroke_width, res_ratio)
        draw.text((x0, top), str(i), COLORS.BLUE, font=arial_font)
    return annotated


def visualize_table_finder_result(
    page,
    fill=DEFAULT_FILL,
    stroke=DEFAULT_STROKE,
    stroke_width=1,
    fontsize=15,
    resolution=150,
    option={"snap_tolerance": 1e-2},
):
    res_ratio = resolution / DEFAULT_RESOLUTION
    table_finder = page.debug_tablefinder2(option)
    im = page.to_image(resolution=resolution).original
    annotated = PIL.Image.new(im.mode, im.size)
    annotated.paste(im)
    try:
        arial_font = PIL.ImageFont.truetype("arial.ttf", fontsize)
    except:
        arial_font = PIL.ImageFont.truetype("Arial Unicode.ttf", fontsize)
    draw = PIL.ImageDraw.Draw(annotated, "RGBA")
    for i, table in enumerate(table_finder.tables):
        x0, top, x1, bottom = get_coords_for_plot_rect(
            table.bbox, resolution, stroke_width
        )
        draw_rect(draw, x0, top, x1, bottom, fill, stroke, stroke_width, res_ratio)
        draw.text((x0, top), str(i), COLORS.BLUE, font=arial_font)
    return annotated


def get_coords_for_plot_rect(bbox, resolution, stroke_width):
    x0, top, x1, bottom = bbox
    x0 = x0 * resolution / DEFAULT_RESOLUTION
    top = top * resolution / DEFAULT_RESOLUTION
    x1 = x1 * resolution / DEFAULT_RESOLUTION
    bottom = bottom * resolution / DEFAULT_RESOLUTION
    half = stroke_width / 2
    x0 += half
    top += half
    x1 -= half
    bottom -= half
    return x0, top, x1, bottom


def draw_rect(draw, x0, top, x1, bottom, fill, stroke, stroke_width, res_ratio):
    draw.rectangle((x0, top, x1, bottom), fill, COLORS.TRANSPARENT)
    if stroke_width > 0:
        segments = [
            ((x0, top), (x1, top)),  # top
            ((x0, bottom), (x1, bottom)),  # bottom
            ((x0, top), (x0, bottom)),  # left
            ((x1, top), (x1, bottom)),  # right
        ]
        for segment in segments:
            draw.line(segment, fill=stroke, width=int(2 * res_ratio))
