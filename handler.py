import json

import grequests
import sys

from geop import geo_utils, geoprocessing
from serializers import gfw_api
from utilities import util, lulc_util

glad_raster = 's3://palm-risk-poc/data/glad/data.vrt'


def umd_loss_gain(event, context):

    geom, area_ha = util.get_shapely_geom(event)
    payload = {'geojson': json.loads(event['body'])['geojson']}

    params = event.get('queryStringParameters')
    if not params:
        params = {}

    thresh = int(params.get('thresh', 30))
    params['thresh'] = thresh

    valid_thresh = [10, 30, 90]

    if thresh not in valid_thresh:
        thresh_str = ', '.join([str(x) for x in valid_thresh])
        msg = 'thresh {} supplied, for this S3 endpoint must be one of {}'.format(thresh, thresh_str)
        return gfw_api.api_error(msg)

    url = 'https://0yvx7602sb.execute-api.us-east-1.amazonaws.com/dev/analysis'
    request_list = []

    # add specific analysis type for each request
    #for analysis_type in ['loss', 'gain', 'extent']:
    for analysis_type in ['loss']:
        new_params = params.copy()
        new_params['analysis'] = analysis_type

        request_list.append(grequests.post(url, json=payload, params=new_params))

    # execute these requests in parallel
    #response_list = grequests.map(request_list, size=3)
    print "calling analysis"
    print request_list
    response_list = grequests.map(request_list, size=1)
    #return gfw_api.serialize_loss_gain(response_list, area_ha)


def analysis(event, context, analysis_raster=None, area_raster=None):

    geom, _ = util.get_shapely_geom(event)
    analysis_type = event['queryStringParameters']['analysis']
    thresh = event['queryStringParameters']['thresh']

    if not analysis_raster:
        ras_dict = {'loss': 's3://gfw2-data/forest_change/hansen_2016_masked_{}tcd/data.vrt'.format(thresh),
                    'extent': 's3://gfw2-data/forest_cover/2000_treecover/data.vrt',
                    'gain': 's3://gfw2-data/forest_change/tree_cover_gain/gaindata_2012/data.vrt'}

        area_raster = 's3://gfw2-data/analyses/area_28m/data.vrt'

        analysis_raster = ras_dict[analysis_type]

    stats = geoprocessing.count_pairs(geom, [analysis_raster, area_raster])

    # unpack the response from the gp function to standard {year: area} dict
    hist = util.unpack_count_histogram(analysis_type, stats)

    return gfw_api.serialize_analysis(hist, event)


def landcover(event, context):

    geom, area_ha = util.get_shapely_geom(event)

    params = event['queryStringParameters']
    if not params:
        params = {}

    layer_name = params.get('layer')

    valid_layers = lulc_util.get_valid_layers()

    if layer_name not in valid_layers:
        msg = 'Layer query param must be one of: {}'.format(', '.join(valid_layers))
        return gfw_api.api_error(msg)

    lulc_raster = lulc_util.ras_lkp(layer_name)
    area_raster = 's3://gfw2-data/analyses/area_28m/data.vrt'
    stats = geoprocessing.count_pairs(geom, [lulc_raster, area_raster])

    hist = util.unpack_count_histogram('landcover', stats)

    return gfw_api.serialize_landcover(hist, layer_name, area_ha)


def loss_by_landcover(event, context):

    geom, area_ha = util.get_shapely_geom(event)

    params = event['queryStringParameters']
    if not params:
        params = {}

    layer_name = params.get('layer')

    valid_layers = lulc_util.get_valid_layers()

    if layer_name not in valid_layers:
        msg = 'Layer query param must be one of: {}'.format(', '.join(valid_layers))
        return gfw_api.api_error(msg)

    lulc_raster = lulc_util.ras_lkp(layer_name)
    loss_raster = 's3://gfw2-data/forest_change/hansen_2016_masked_30tcd/data.vrt'
    area_raster = 's3://gfw2-data/analyses/area_28m/data.vrt'

    raster_list = [lulc_raster, loss_raster, area_raster]
    stats = geoprocessing.count_pairs(geom, raster_list)

    hist = util.unpack_count_histogram('loss-by-landcover', stats)

    return gfw_api.serialize_loss_by_landcover(hist, area_ha, event)


def glad_alerts(event, context, ras=glad_raster):

    geom, area_ha = util.get_shapely_geom(event)
    payload = {'geojson': json.loads(event['body'])['geojson']}

    try:
        params = util.validate_glad_params(event)
    except ValueError, e:
        return gfw_api.api_error(str(e))

    stats = geoprocessing.count(geom, ras)

    hist = util.unpack_glad_histogram(stats, params)

    return gfw_api.serialize_glad(hist, area_ha, params['aggregate_by'], params['period'])


if __name__ == '__main__':

    aoi = {"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[100.05523681640625,62.710684552498556],[99.964599609375,62.63250704195784],[100.1678466796875,62.629981748883736],[100.05523681640625,62.710684552498556]]]}}]}
    #aoi = {"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[22.241821289062496,2.5260367521718403],[22.1319580078125,1.9771465537125772],[22.664794921874996,1.9716566508363325],[22.8570556640625,2.4711573377481715],[22.241821289062496,2.5260367521718403]]]}}]}

    # why this crazy structure? Oh lambda . . . sometimes I wonder
    event = {
             'body': json.dumps({'geojson': aoi}),
             'queryStringParameters': {'aggregate_values': True, 'aggregate_by': 'day', 'thresh': '30', 'period':'2016-01-01,2017-01-01'}
            }


    glad_alerts(event, None)
    #analysis(event, None, loss_raster, area_raster)
    #landcover(event, None)
    #loss_by_landcover(event, None)
    #umd_loss_gain(event, None)
