import numpy as np

from geop.geo_utils import mask_geom_on_raster


def count_pairs(geom, raster_paths):
    """
    Perform a cell count analysis on groupings of cells from 2 rasters stacked
    on top of each other.

    Args:
        geom (Shapley Geometry): A polygon in the same SRS as `raster_path`
            which will define the area of analysis to count cell values.

        raster_paths (list<string>): Two local file paths to geographic rasters
            containing values to group and count.

    Returns:
        pairs (dict): Grouped pairs as key with count of number of occurrences
            within the two rasters masked by geom
            ex:  { cell1_rastA::cell1_rastB: 42 }
    """

    # Read in two rasters and mask geom on both of them
    layers = tuple(mask_geom_on_raster(geom, raster_path)[0]
                   for raster_path in raster_paths)

    if len(layers) == 3:
        combined_layer = layers[0] * 500 + layers[1]
        layers = [combined_layer, layers[2]]

    # Take the two masked arrays, and stack them along the third axis
    # Effectively: [[cell_1a, cell_1b], [cell_2a, cell_2b], ..],[[...]]
    pairs = np.ma.dstack(layers)

    # Get the array in 2D form
    arr = pairs.reshape(-1, pairs.shape[-1])

    # Remove Rows which have masked values
    trim_arr = np.ma.compress_rowcols(arr, 0)

    if len(trim_arr):

        # Lexicographically sort so that repeated pairs follow one another
        sorted_arr = trim_arr[np.lexsort(trim_arr.T), :]

        # otherwise no overlap between the two rasters
        if len(sorted_arr):

            # The difference between index n and n+1 in sorted_arr, for each index.
            # Since it's sorted, repeated entries will have a value of 0 at that index
            diff_sort = np.diff(sorted_arr, axis=0)

            # True or False value for each index of diff_sort based on a diff_sort
            # having truthy or falsey values.  Indexes with no change (0 values) will
            # be represented as False in this array
            indexes_changed_mask = np.any(diff_sort, 1)

            # Get the indexes that are True, indicating an index of sorted_arr that has
            # a difference with its preceding value - ie, it represents a new
            # occurrence of a value
            diff_indexes = np.where(indexes_changed_mask)[0]

            # Get the rows at the diff indexes, these are unique at each index
            unique_rows = [sorted_arr[i] for i in diff_indexes] + [sorted_arr[-1]]

            # Prepend a -1 on the list of diff_indexes and append the index of the last
            # unique row, resulting in an array of index changes with fenceposts on
            # both sides.  ie, `[-1, ...list of diff indexes..., <idx of last sorted>]`
            idx_of_last_val = sorted_arr.shape[0] - 1
            diff_idx_with_start = np.insert(diff_indexes, 0, -1)
            fencepost_diff_indexes = np.append(diff_idx_with_start, idx_of_last_val)

            # Get the number of occurrences of each unique row based on the difference
            # between the indexes at which they change.  Since we put fenceposts up,
            # we'll get a count for the first and last elements of the diff indexes
            counts = np.diff(fencepost_diff_indexes)

            # Map the pairs to the count, compressing values to keys in this format:
            #   cell_r1::cell_r2
            pair_counts = zip(unique_rows, counts)
            pair_map = {k[0].astype(str) + '::' + k[1].astype(str): cnt for k, cnt in pair_counts}

        else:
            pair_map = {}
    else:
        pair_map = {}

    return pair_map
