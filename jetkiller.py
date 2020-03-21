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
_default_ignore_gray = True

pygtk.require("2.0")


def get_colormap(colormap):
    """Return a colormap as an array. `colormap` is any name recognized by matplotlib."""
    min_val = 0
    max_val = 1
    cmap = cm.get_cmap(colormap, _colormap_size)
    data = np.linspace(min_val, max_val, _colormap_size)
    color_table = np.around(cmap(data) * _nint)
    return np.array(color_table[:, 0:3], dtype=_type)


def jetkiller(img, colormap, ignore_gray):
    img.undo_group_start()
    gimp.progress_init("Executing Jet Killer ...")

    src_layer = img.active_layer
    w = src_layer.width
    h = src_layer.height
    dst_layer = gimp.Layer(img, src_layer.name + " - Jet Killer", w, h, gimpenums.RGBA_IMAGE)
    dst_layer.set_offsets(*src_layer.offsets)  # at the same position as the source
    img.add_layer(dst_layer)  # on top by default

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
    src_rgn = src_layer.get_pixel_rgn(0, 0, src_layer.width, src_layer.height, False, False)
    dst_rgn = dst_layer.get_pixel_rgn(0, 0, dst_layer.width, dst_layer.height, True, True)

    for x in xrange(src_layer.width):
        for y in xrange(src_layer.height):
            pixel = src_rgn[x, y]
            if not ignore_gray or (pixel[0] != pixel[1] or pixel[1] != pixel[2]):
                new_rgb_pixel = convert_pixel(pixel[0:3])
                if len(pixel) == 4:  # has an alpha channel
                    new_rgba_pixel = new_rgb_pixel + pixel[3]
                else:
                    new_rgba_pixel = new_rgb_pixel + chr(255)
                dst_rgn[x, y] = new_rgba_pixel

        gimp.progress_update(float(x) / src_layer.width)  # update progress bar

    dst_layer.flush()
    dst_layer.merge_shadow()
    dst_layer.update(0, 0, dst_layer.width, dst_layer.height)

    gimp.pdb.gimp_progress_end()  # important for non-interactive mode
    gimp.displays_flush()
    img.undo_group_end()


class Dialog:
    def __init__(self, img, colormap, ignore_gray):

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
        self.colormap = colormap
        try:
            idx = colormaps.index(self.colormap)
            self.cm_combobox.set_active(idx)
        except ValueError:  # should not happen, as the default colormap should exist
            self.cm_combobox.set_active(0)

        self.dialog.vbox.pack_start(self.cm_combobox, False, False, 0)
        self.cm_combobox.show()

        # Ignore gray checkbox
        self.ignore_gray = ignore_gray
        self.gray_checkbutton = gtk.CheckButton("Ignore gray pixels")
        self.gray_checkbutton.set_active(self.ignore_gray)
        self.gray_checkbutton.show()
        self.dialog.vbox.pack_start(self.gray_checkbutton, True, True, 0)

        # Close button
        button_close = gtk.Button(stock=gtk.STOCK_CLOSE)
        self.dialog.action_area.pack_start(button_close, True, True, 0)
        button_close.show()

        # OK button
        button_ok = gtk.Button(stock=gtk.STOCK_OK)
        self.dialog.action_area.pack_start(button_ok, True, True, 0)
        button_ok.show()

        # Events
        button_ok.connect("clicked", self.on_click_ok)
        button_close.connect("clicked", self.close_action)

        self.quit = False  # changed to true when dialog closed
        gtk.main()

    def on_click_ok(self, arg):
        self.colormap = self.cm_combobox.get_active_text()
        self.ignore_gray = self.gray_checkbutton.get_active()
        self.dialog.destroy()
        gtk.main_quit()

    def close_action(self, arg):
        self.quit = True
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
                       (gimpenums.PDB_IMAGE, "image", "Input image"),
                       (gimpenums.PDB_STRING, "colormap", "Output colormap (from matplotlib)"),
                       (gimpenums.PDB_INT32, "ignore_gray", "If true, ignore gray pixels")]
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

    # Note: keyword arguments are not passed in interactive mode, but are mandatory (and actually non-keyword)
    #       when in non-interactive mode.
    def jetkiller(self, run_mode, image, colormap=_default_colormap, ignore_gray=_default_ignore_gray):
        # Retrieve shelved parameters
        try:
            prev_colormap = gimpshelf.shelf['colormap']
            prev_ignore_gray = gimpshelf.shelf['ignore_gray']
        except KeyError:
            prev_colormap = _default_colormap
            prev_ignore_gray = _default_ignore_gray

        if run_mode == gimpenums.RUN_INTERACTIVE:
            dialog = Dialog(image, prev_colormap, prev_ignore_gray)
            if dialog.quit:
                return
            jetkiller(image, dialog.colormap, dialog.ignore_gray)
            # Shelf parameters
            gimpshelf.shelf['colormap'] = dialog.colormap
            gimpshelf.shelf['ignore_gray'] = dialog.ignore_gray
        elif run_mode == gimpenums.RUN_NONINTERACTIVE:
            jetkiller(image, colormap, ignore_gray)
        elif run_mode == gimpenums.RUN_WITH_LAST_VALS:
            jetkiller(image, prev_colormap, prev_ignore_gray)
        else:
            raise ValueError("Invalid run mode. "
                             "Should be RUN_INTERACTIVE (0), RUN_NONINTERACTIVE (1) or RUN_WITH_LAST_VALS (2).")


if __name__ == '__main__':
    Jetkiller().start()
