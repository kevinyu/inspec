import os

import numpy as np

from inspec.colormap import VALID_CMAPS, load_cmap
from inspec.io import AudioReader
from inspec.maps import (
    Char,
    FullCharMap,
    HalfCharMap,
    QuarterCharMap,
)
from inspec.render import StdoutRenderer
from inspec.transform import (
    SpectrogramTransform,
    AmplitudeEnvelopeTwoSidedTransform,
)


def run_all_tests():
    data, sampling_rate, metadata = AudioReader.read_file(
        "/home/kevin/Projects/inspec/sample_files/BluWhi3230M_So_03.wav"
    )

    renderer = StdoutRenderer

    all_maps = [
        FullCharMap,
        HalfCharMap,
        QuarterCharMap,
    ]

    all_transforms = [
        SpectrogramTransform(1000, 50, min_freq=250, max_freq=10000),
        AmplitudeEnvelopeTwoSidedTransform(gradient=(0.2, 0.8)),
    ]

    cmap_names = VALID_CMAPS

    for Map in all_maps:
        for transform in all_transforms:
            for cmap_name in cmap_names:
                cmap = load_cmap(cmap_name)
                if cmap_name.endswith("_r"):
                    continue
                print("Running {} with {} using cmap {}".format(Map, transform, cmap_name))
                termsize = os.get_terminal_size()
                desired_size = Map.max_img_shape(termsize.lines // 2, termsize.columns // 2)
                print("Attemping size {}".format(desired_size))
                img, metadata = transform.convert(data, sampling_rate, output_size=desired_size)
                char_array = Map.to_char_array(img)
                char_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)
                StdoutRenderer.render(char_array)
