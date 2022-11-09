import random

import PIL
from openslide.deepzoom import DeepZoomGenerator

from PIL import Image


class MaskDeepZoomGenerator(DeepZoomGenerator):
    def __init__(self, lock, mask_image, osr, tile_size=254, overlap=1, limit_bounds=False):
        super(MaskDeepZoomGenerator, self).__init__(osr, tile_size, overlap, limit_bounds)

        mask = Image.new('RGBA', mask_image.size, color=(255, 255, 255, 80))
        mask_image = PIL.ImageChops.multiply(mask_image, mask)

        self.mask_image = mask_image  # .convert('RGB')

        if mask_image:
            self.lock = lock
            self.svs_full_size = eval(mask_image.info['svs-full-size'])
            self.refactor_size = tuple([ (1.0 * self.svs_full_size[i] / self.mask_image.size[i]) for i in range(2)])
            #self.refactor_size = eval(mask_image.info['resize-factor'])

    def get_tile(self, level, address):
        """Return an RGB PIL.Image for a tile.

        level:     the Deep Zoom level.
        address:   the address of the tile within the level as a (col, row)
                   tuple."""

        # Read tile
        args, z_size = self._get_tile_info(level, address)
        tile = self._osr.read_region(*args)

        # Apply on solid background
        bg = Image.new('RGB', tile.size, self._bg_color)
        tile = Image.composite(tile, bg, tile)

        if self.mask_image:
            dim0 = self._l_dimensions[0]
            dimtile = self._l_dimensions[args[1]]
            tile_resize_factor = tuple([ (1.0 * dim0[i] / dimtile[i]) for i in range(2)])

            tile_loc_0 = args[0]

            tile_loc_mask = tuple([ int(tile_loc_0[i] / self.refactor_size[i]) for i in range(2)])
            tile_size_mask = tuple([ int(tile.size[i] * tile_resize_factor[i] / self.refactor_size[i]) for i in range(2)])
            box = (tile_loc_mask[0],
                   tile_loc_mask[1],
                   tile_loc_mask[0] + tile_size_mask[0],
                   tile_loc_mask[1] + tile_size_mask[1])  # left upper right lower 0, 0, 2893,2377

            # PIL is not threadsafe
            self.lock.acquire()
            tile_mask = self.mask_image.crop(box=box)
            self.lock.release()

            tile_mask_resized = tile_mask.resize(tile.size, PIL.Image.NEAREST)

            #tile = Image.blend(tile, tile_mask_resized, alpha=0.1)
            tile = Image.composite(tile_mask_resized, tile, tile_mask_resized)
        # Scale to the correct size
        if tile.size != z_size:
            tile.thumbnail(z_size, Image.ANTIALIAS)

        return tile