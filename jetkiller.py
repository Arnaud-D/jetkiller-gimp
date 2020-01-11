#!/usr/bin/env python

from gimpfu import *
import numpy as np
from matplotlib import cm

# Internal package parameters
_colormap_size = 512
_nint = 255
_type = float
_cache_size = 1024


def get_colormap(colormap):
    """Return a colormap as an array. `colormap` is any name recognized by matplotlib."""
    min_val = 0
    max_val = 1
    cmap = cm.get_cmap(colormap, _colormap_size)
    data = np.linspace(min_val, max_val, _colormap_size)
    color_table = np.around(cmap(data) * _nint)
    return np.array(color_table[:, 0:3], dtype=_type)


def jetkiller(img, drw) :
    pdb.gimp_image_undo_group_start(img)  # start undo group
    gimp.progress_init("Jet Killer in progress...")

    active_layer = pdb.gimp_image_get_active_layer(img)
    new_layer = pdb.gimp_layer_new(img,
                                   active_layer.width,
                                   active_layer.height,
                                   RGBA_IMAGE,
                                   active_layer.name + " - Jet Killer",
                                   100.,
                                   NORMAL_MODE)
    pdb.gimp_image_insert_layer(img, new_layer, None, 0)

    (selection_exists, start_x, start_y, end_x, end_y) = pdb.gimp_selection_bounds(img)
    if not selection_exists:
        pdb.gimp_selection_all(img)
        (_, start_x, start_y, end_x, end_y) = pdb.gimp_selection_bounds(img)

    input_cmap = get_colormap("jet")
    output_cmap = get_colormap("viridis")

    def convert_pixel(red, green, blue):
        # Get nearest color from input colormap and return
        # corresponding color in output colormap
        dr = input_cmap[:, 0] - red
        dg = input_cmap[:, 1] - green
        db = input_cmap[:, 2] - blue
        dist = dr * dr + dg * dg + db * db
        idx = np.argmin(dist)
        return output_cmap[idx]

    for y in range(start_y, end_y + 1):
        for x in range(start_x, end_x + 1):
            if pdb.gimp_selection_value(img, x, y) > 0:  # not selected pixels are ignored
                (nchannels, pixel_value) = pdb.gimp_drawable_get_pixel(drw, x, y)
                r, g, b = pixel_value[0:3]
                if r != g or g != b:  # Grey pixels are not processed
                    (new_r, new_g, new_b) = convert_pixel(r, g, b)
                    if nchannels == 4:
                        new_pixel_value = (new_r, new_g, new_b, pixel_value[3])
                    else:
                        new_pixel_value = (new_r, new_g, new_b, 255)
                    pdb.gimp_drawable_set_pixel(new_layer, x, y, 4, new_pixel_value)

        new_layer.update(0, 0, drw.width, drw.height)

        gimp.progress_update(float(y - start_y) / (end_y - start_y + 1))  # update progress bar
        pdb.gimp_displays_flush()

    if not selection_exists:  # remove selection when added by the script
        pdb.gimp_selection_none(img)

    pdb.gimp_displays_flush()
    pdb.gimp_image_undo_group_end(img)  # end undo group


register(
    "python_fu_jetkiller",
    "Improve an image using the 'jet' colormap",
    "Improve an image using the 'jet' colormap by converting it to the 'viridis' colormap",
    "Arnaud-D",
    "Arnaud-D",
    "2020",
    "Jet Killer",
    "RGB*",
    [
        (PF_IMAGE, "image", "Input image", None),
        (PF_DRAWABLE, "drawable", "Input drawable", None),
    ],
    [],
    jetkiller, menu="<Image>/Filters/Enhance")

main()
