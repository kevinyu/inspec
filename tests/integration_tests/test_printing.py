import os

import numpy as np

from inspec.colormap import list_cmap_names, load_cmap
from inspec.io import AudioReader
from inspec.maps import MapType, get_map
from inspec.render import StdoutRenderer
from inspec.transform import (
    SpectrogramTransform,
    AmplitudeEnvelopeTwoSidedTransform,
)


def run_all_tests(sample_audio_file):
    audio_data = AudioReader.read_file(sample_audio_file)

    renderer = StdoutRenderer

    all_transforms = [
        SpectrogramTransform(1000, 50, min_freq=250, max_freq=10000),
        AmplitudeEnvelopeTwoSidedTransform(gradient=(0.2, 0.8)),
    ]

    cmap_names = list_cmap_names()

    for map_type in (MapType.Full, MapType.Half, MapType.Quarter):
        mapper = get_map(map_type)
        for transform in all_transforms:
            for cmap_name in cmap_names:
                cmap = load_cmap(cmap_name)
                if cmap_name.endswith("_r"):
                    continue
                print("Running {} with {} using cmap {}".format(mapper, transform, cmap_name))
                termsize = os.get_terminal_size()
                desired_size = mapper.max_img_shape(termsize.lines // 2, termsize.columns // 2)
                print("Attemping size {}".format(desired_size))
                img, metadata = transform.convert(
                    audio_data.data,
                    audio_data.sampling_rate,
                    output_size=desired_size
                )
                char_array = mapper.to_char_array(img)
                char_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)
                StdoutRenderer.render(char_array)
