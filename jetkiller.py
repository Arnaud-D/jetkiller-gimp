#!/usr/bin/env python

import gimp
import gimpenums
import gimpplugin
import gimpshelf

import pygtk
import gtk
import numpy as np
from matplotlib import cm

# Internal package parameters
_colormap_size = 512
_nint = 255
_type = int
_cache_size = 1024
_tile_cache_size = 16
_default_colormap = "viridis"

pygtk.require("2.0")


def get_colormap(colormap):
    """Return a colormap as an array. `colormap` is any name recognized by matplotlib."""
    min_val = 0
    max_val = 1
    cmap = cm.get_cmap(colormap, _colormap_size)
    data = np.linspace(min_val, max_val, _colormap_size)
    color_table = np.around(cmap(data) * _nint)
    return np.array(color_table[:, 0:3], dtype=_type)


def jetkiller(img, colormap):
    gimp.pdb.gimp_image_undo_group_start(img)  # start undo group
    gimp.progress_init("Executing Jet Killer ...")

    active_layer = gimp.pdb.gimp_image_get_active_layer(img)
    new_layer = gimp.pdb.gimp_layer_new(img,
                                        active_layer.width,
                                        active_layer.height,
                                        gimpenums.RGBA_IMAGE,
                                        active_layer.name + " - Jet Killer",
                                        100.,
                                        gimpenums.NORMAL_MODE)
    gimp.pdb.gimp_image_insert_layer(img, new_layer, None, 0)

    (selection_exists, start_x, start_y, end_x, end_y) = gimp.pdb.gimp_selection_bounds(img)
    if not selection_exists:
        gimp.pdb.gimp_selection_all(img)
        (_, start_x, start_y, end_x, end_y) = gimp.pdb.gimp_selection_bounds(img)

    input_cmap = get_colormap("jet")
    output_cmap = get_colormap(colormap)

    def raw_convert_pixel(px):
        # Get nearest color from input colormap and return
        # corresponding color in output colormap
        dr = input_cmap[:, 0] - ord(px[0])
        dg = input_cmap[:, 1] - ord(px[1])
        db = input_cmap[:, 2] - ord(px[2])
        dist = dr * dr + dg * dg + db * db
        idx = np.argmin(dist)
        return "".join([chr(k) for k in output_cmap[idx]])

    cache = {}

    def convert_pixel(px):
        if px not in cache:
            cache[px] = raw_convert_pixel(px)
        return cache[px]

    gimp.tile_cache_ntiles(_tile_cache_size)
    src_rgn = active_layer.get_pixel_rgn(start_x, start_y, end_x - start_x, end_y - start_y, False, False)
    dst_rgn = new_layer.get_pixel_rgn(start_x, start_y, end_x - start_x, end_y - start_y, True, True)

    for x in xrange(start_x, end_x):
        for y in xrange(start_y, end_y):
            pixel = src_rgn[x, y]
            if pixel[0] != pixel[1] or pixel[1] != pixel[2]:  # Grey pixels are not processed
                new_pixel = convert_pixel(pixel[0:3])
                if len(pixel) == 4:  # number of channels
                    new_pixel_value = new_pixel + pixel[3]
                else:
                    new_pixel_value = new_pixel + chr(255)
                dst_rgn[x, y] = new_pixel_value

        progress_ratio = float(x - start_x) / (end_x - start_x)
        gimp.progress_update(progress_ratio)  # update progress bar

    new_layer.flush()
    new_layer.merge_shadow()
    new_layer.update(start_x, start_y, end_x - start_x, end_y - start_y)

    if not selection_exists:  # remove selection when added by the script
        gimp.pdb.gimp_selection_none(img)

    gimp.pdb.gimp_progress_end()
    gimp.pdb.gimp_displays_flush()
    gimp.pdb.gimp_image_undo_group_end(img)  # end undo group


class Dialog:
    def __init__(self, img):

        # Dialog configuration
        self.dialog = gtk.Dialog()
        self.dialog.set_title("Jet Killer")
        self.dialog.set_border_width(10)
        self.dialog.show()

        # Colormap selector
        # --- Label
        cm_label = gtk.Label("Choose an output colormap:")
        cm_label.show()
        self.dialog.vbox.pack_start(cm_label, True, True, 0)

        # --- ComboBox
        self.cm_combobox = gtk.ComboBox()
        self.store = gtk.ListStore(str)
        cell = gtk.CellRendererText()
        self.cm_combobox.pack_start(cell)
        self.cm_combobox.add_attribute(cell, 'text', 0)
        colormaps = ["viridis", "plasma", "inferno", "magma", "cividis"]
        for c in colormaps:
            self.store.append([c])
        self.cm_combobox.set_model(self.store)
        try:
            self.colormap = gimpshelf.shelf['colormap']
        except KeyError:
            self.colormap = _default_colormap
        try:
            idx = colormaps.index(self.colormap)
            self.cm_combobox.set_active(idx)
        except ValueError:  # should not happen, as the default colormap should exist
            self.cm_combobox.set_active(0)

        self.dialog.vbox.pack_start(self.cm_combobox, False, False, 0)
        self.cm_combobox.show()

        # Close button
        button_close = gtk.Button(stock=gtk.STOCK_CLOSE)
        self.dialog.action_area.pack_start(button_close, True, True, 0)
        button_close.show()

        # OK button
        button_ok = gtk.Button(stock=gtk.STOCK_OK)
        self.dialog.action_area.pack_start(button_ok, True, True, 0)
        button_ok.show()

        # Events
        self.dialog.connect("destroy", gtk.main_quit)
        button_ok.connect("clicked", self.on_click_ok)
        button_close.connect_object("clicked", gtk.Widget.destroy, self.dialog)

        gtk.main()

    def on_click_ok(self, arg):
        self.colormap = self.cm_combobox.get_active_text()
        self.dialog.destroy()
        gtk.main_quit()


class Jetkiller(gimpplugin.plugin):
    def __init__(self):
        self.name = "jetkiller"
        self.blurb = "Improve an image using the 'jet' colormap"
        self.help = "Improve an image using the 'jet' colormap by converting it to a better colormap"
        self.author = "Arnaud-D"
        self.copyright = self.author
        self.date = "2020"
        self.menupath = "<Image>/Filters/Enhance/Jet Killer..."
        self.image_types = "RGB*"
        self.type = gimpenums.PLUGIN
        self.params = [(gimpenums.PDB_INT32, "run-mode", "Run mode"),
                       (gimpenums.PDB_IMAGE, "image", "Input image")]
        self.ret_vals = []

    def query(self):
        gimp.install_procedure(
            self.name,
            self.blurb,
            self.help,
            self.author,
            self.copyright,
            self.date,
            self.menupath,
            self.image_types,
            self.type,
            self.params,
            self.ret_vals)

    def jetkiller(self, run_mode, image):
        if run_mode == gimpenums.RUN_INTERACTIVE:
            dialog = Dialog(image)
            colormap = dialog.colormap
        elif run_mode == gimpenums.RUN_NONINTERACTIVE:
            raise NotImplementedError("Non-interactive mode is not implemented (yet).")
        elif run_mode == gimpenums.RUN_WITH_LAST_VALS:
            colormap = gimpshelf.shelf['colormap']
        else:
            raise ValueError("Invalid run mode. "
                             "Should be RUN_INTERACTIVE (0), RUN_NONINTERACTIVE (1) or RUN_WITH_LAST_VALS (2).")

        jetkiller(image, colormap)
        gimpshelf.shelf['colormap'] = colormap


if __name__ == '__main__':
    Jetkiller().start()
