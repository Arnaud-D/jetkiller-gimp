#!/usr/bin/env python

import pygtk
import gtk
import numpy as np
from matplotlib import cm
import gimpfu as gf

pygtk.require("2.0")

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


def jetkiller(img, colormap):
    gf.pdb.gimp_image_undo_group_start(img)  # start undo group
    gf.gimp.progress_init("Executing Jet Killer (0%)")

    active_layer = gf.pdb.gimp_image_get_active_layer(img)
    new_layer = gf.pdb.gimp_layer_new(img,
                                      active_layer.width,
                                      active_layer.height,
                                      gf.RGBA_IMAGE,
                                      active_layer.name + " - Jet Killer",
                                      100.,
                                      gf.NORMAL_MODE)
    gf.pdb.gimp_image_insert_layer(img, new_layer, None, 0)

    (selection_exists, start_x, start_y, end_x, end_y) = gf.pdb.gimp_selection_bounds(img)
    if not selection_exists:
        gf.pdb.gimp_selection_all(img)
        (_, start_x, start_y, end_x, end_y) = gf.pdb.gimp_selection_bounds(img)

    input_cmap = get_colormap("jet")
    output_cmap = get_colormap(colormap)

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
            if gf.pdb.gimp_selection_value(img, x, y) > 0:  # not selected pixels are ignored
                (nchannels, pixel_value) = gf.pdb.gimp_drawable_get_pixel(active_layer, x, y)
                r, g, b = pixel_value[0:3]
                if r != g or g != b:  # Grey pixels are not processed
                    (new_r, new_g, new_b) = convert_pixel(r, g, b)
                    if nchannels == 4:
                        new_pixel_value = (new_r, new_g, new_b, pixel_value[3])
                    else:
                        new_pixel_value = (new_r, new_g, new_b, 255)
                    gf.pdb.gimp_drawable_set_pixel(new_layer, x, y, 4, new_pixel_value)

        new_layer.update(0, 0, active_layer.width, active_layer.height)

        progress_ratio = float(y - start_y) / (end_y - start_y + 1)
        gf.gimp.progress_update(progress_ratio)  # update progress bar
        gf.pdb.gimp_progress_set_text("Executing Jet Killer ({:.1f}%)".format(progress_ratio * 100))
        gf.pdb.gimp_displays_flush()

    if not selection_exists:  # remove selection when added by the script
        gf.pdb.gimp_selection_none(img)

    gf.pdb.gimp_progress_end()
    gf.pdb.gimp_displays_flush()
    gf.pdb.gimp_image_undo_group_end(img)  # end undo group


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
        button_close.connect_object("clicked", gtk.Widget.destroy, self)

        self.img = img
        gtk.main_iteration()

    def on_click_ok(self, arg):
        gtk.main_quit()
        colormap = self.cm_combobox.get_active_text()
        jetkiller(self.img, colormap)


class JetkillerPlugin:
    def __init__(self):
        self.proc_name = "python_fu_jetkiller"
        self.blurb = "Improve an image using the 'jet' colormap"
        self.help = "Improve an image using the 'jet' colormap by converting it to a better colormap"
        self.author = "Arnaud-D"
        self.copyright = self.author
        self.date = "2020"
        self.label = "Jet Killer"
        self.imagetypes = "RGB*"
        self.params = [(gf.PF_IMAGE, "image", "Input image", None)]
        self.results = []
        self.menu = "<Image>/Filters/Enhance"

    def register(self):
        gf.register(
            self.proc_name,
            self.blurb,
            self.help,
            self.author,
            self.copyright,
            self.date,
            self.label,
            self.imagetypes,
            self.params,
            self.results,
            self.function,
            menu=self.menu
        )

    def function(self, img):  # number of arguments (excluding self) should be len(self.params)
        dialog = Dialog(img)
        gtk.main()


jetkiller_plugin = JetkillerPlugin()
jetkiller_plugin.register()
gf.main()
