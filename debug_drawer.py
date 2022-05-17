"""
developing
"""


import locale
import os
import subprocess

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

import pdfplumber


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
    bboxes,
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
    for i, bbox in enumerate(bboxes):
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
    option={},
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


def one_page_pdf_to_result_png_with_ghost_script(
    pdf_path,
    temp_local_dir,
    fill=DEFAULT_FILL,
    stroke=DEFAULT_STROKE,
    stroke_width=1,
    fontsize=15,
    resolution: int = 150,
    option={},
):
    pdf = pdfplumber.open(pdf_path)
    if len(pdf.pages) > 1:
        raise ValueError("PDF need to be a single page.")
    page = pdf.pages[0]

    if type(resolution) != int:
        raise ValueError(f"resolution must be int, not {type(resolution)}.")

    pdf_name = pdf_path.split("/")[-1][:-4]
    print(pdf_name)
    img_path = temp_local_dir + f"{pdf_name}.png"
    args = ["gs", "-sDEVICE=png16m", f"-r{resolution}", "-o", img_path, pdf_path]

    # args = [
    #     "gs",
    #     "-sDEVICE=png16m",
    #     f"-r{300}",
    #     "-o", '"/Users/ryosuke/AEMC/gcf-table-extractor/textbook_rawdata/11111111-test/asdf.png"',
    #     '"/Users/ryosuke/AEMC/gcf-table-extractor/textbook_rawdata/11111111-test/test_one_page.pdf"'
    #     ]
    # gs -sDEVICE=png16m -r300 -o aaa.png test_one_page.pdf

    subprocess.run(args)

    annotated = PIL.Image.open(img_path)
    try:
        resolution = annotated.info["dpi"][0]
        if annotated.info["dpi"][0] != annotated.info["dpi"][1]:
            raise ValueError("dpi must be the same for the row/col directions.")
    except:
        pass
    res_ratio = resolution / DEFAULT_RESOLUTION

    table_finder = page.debug_tablefinder2(option)

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

    try:
        os.remove(img_path)
    except:
        pass

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
