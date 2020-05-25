#!/usr/bin/python
# -*- coding: UTF-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. */

# Authors:
# Michael Berg-Mohnicke <michael.berg@zalf.de>
# Tommaso Stella <tommaso.stella@zalf.de>
#
# Maintainers:
# Currently maintained by the authors.
#
# This file has been created at the Institute of
# Landscape Systems Analysis at the ZALF.
# Copyright (C: Leibniz Centre for Agricultural Landscape Research (ZALF)

import time
import json
import copy
from datetime import date, datetime, timedelta
from collections import defaultdict
import sys
import zmq
import monica_io3
import rotate_script

USER = "remoteProducer-remoteMonica"
LOCAL_RUN = False

PATHS = {
    "hampf": {
        "INCLUDE_FILE_BASE_PATH": "C:/Users/hampf/Documents/GitHub/czech_globe",
        "LOCAL_ARCHIVE_PATH_TO_PROJECT": "C:/Users/hampf/Documents/GitHub/Europ_Crop_Rot/macsur-croprotations-cz_rerunStepB/converted/", 
    },
    "local-remote": {
        "INCLUDE_FILE_BASE_PATH": "C:/Users/hampf/Documents/GitHub/czech_globe/",
        "ARCHIVE_PATH_TO_PROJECT": "/monica_data/climate-data/EU-RotEns/", ## points to the climate data
    },
    "remoteProducer-remoteMonica": {
        "INCLUDE_FILE_BASE_PATH": "/project/", # path to monica-parameters
        "ARCHIVE_PATH_TO_PROJECT": "/monica_data/climate-data/EU-RotEns/", # mounted path to archive accessable by monica executable
        "PATH_TO_DATA_DIR": "./", # mounted path to archive or hard drive with data 
    }
}


def main():
    "main"

    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    config = {
        "port": 6669
    }
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            k,v = arg.split("=")
            if k in config:
                config[k] = int(v)

    if LOCAL_RUN:
        socket.connect("tcp://localhost:" + str(config["port"]))
    else:
        socket.connect("tcp://" + "login01.cluster.zalf.de:" + str(config["port"]))

    base_path = PATHS[USER]["PATH_TO_DATA_DIR"]
    with open(base_path + "/templates/out_stepB.json") as _:
        out_stepB = json.load(_)

    with open(base_path + "/templates/crop_template.json") as _:
        crop_template = json.load(_)

    with open(base_path + "/templates/sim_template.json") as _:
        sim_template = json.load(_)
    
    sites = {}
    with open(base_path + "/soils/universal.json") as _:
        sites["universal"] = json.load(_)
    with open(base_path + "/soils/lednice.json") as _:
        sites["lednice"] = json.load(_)
    with open(base_path + "/soils/milhostov.json") as _:
        sites["milhostov"] = json.load(_)
    with open(base_path + "/soils/mueh.json") as _:
        sites["mueh"] = json.load(_)
    with open(base_path + "/soils/muen.json") as _:
        sites["muen"] = json.load(_)
    with open(base_path + "/soils/oedum.json") as _:
        sites["oedum"] = json.load(_)
    with open(base_path + "/soils/ukkel.json") as _:
        sites["ukkel"] = json.load(_)


    sim = sim_template
    sim["output"]["events"] = out_stepB["my_out"]

    #with open("test.json", 'w') as testfile:
    #    json.dump(sim, testfile)

    #stations = ["BEUKKL",, "CZLEDN", "DKODUM", "GEMUEH", "GEMUEN", "SKMILH"]
    #stations = ["BEUKKL", "CZLEDN"]
    
    #soils = ["universal", "ukkel", "lednice", "oedum", "mueh", "muen", "milhostov"]
    #soils = ["universal"]

    station2soil = {
        "BEUKKL": ["universal", "ukkel"],
        "CZLEDN": ["universal", "lednice"],
        "DKODUM": ["universal", "oedum"],
        "GEMUEH": ["universal", "mueh"],
        "GEMUEN": ["universal", "muen"],
        "SKMILH": ["universal", "milhostov"]
    }

    rotations = rotate_script.generate_rotations(PATHS[USER]["PATH_TO_DATA_DIR"])

    climate_data = [
        "GFDL-CM3",
        "HadGEM2-CC",
        "IPSL-CM5A-LR",
        "MIROC5",
        "NorESM1-M"
    ]

    rcps = [
        "RCP26",
        "RCP85",
    ]

    site_parameters = {
        "BEUKKL": {
           "Latitude": 51.20934,
            "NDeposition": 33
        },
        "CZLEDN": {
            "Latitude": 48.79781,
            "NDeposition": 15
        },
        "DKODUM": {
            "Latitude": 56.31192,
            "NDeposition": 40
        },
        "GEMUEH": {
            "Latitude": 48.24577,
            "NDeposition": 30
        },
        "GEMUEN": {
            "Latitude": 52.50691,
            "NDeposition": 30
        },
        "SKMILH": {
            "Latitude": 48.66545,
            "NDeposition": 30
        }
    }

    counter=1
    start_store = time.perf_counter

    def generate_and_send_env(station, soil_type, rot_id, climate, rcp, realization, counter):
        
        def limit_rootdepth():
            for cultivation_method in env["cropRotation"]:
                for workstep in cultivation_method["worksteps"]:
                    if workstep["type"] == "Seed":
                        current_rootdepth = float(workstep["crop"]["cropParams"]["cultivar"]["CropSpecificMaxRootingDepth"])
                        workstep["crop"]["cropParams"]["cultivar"]["CropSpecificMaxRootingDepth"] = min(current_rootdepth, 0.8)
                        break
                
        crop = copy.deepcopy(crop_template)
        crop["cropRotation"] += rotations[rot_id]
        
        site = sites[soil_type]
        site["SiteParameters"]["Latitude"] = site_parameters[station]["Latitude"]
        site["SiteParameters"]["NDeposition"] = site_parameters[station]["NDeposition"]


        env = monica_io3.create_env_json_from_json_config({
            "crop": crop,
            "site": site,
            "sim": sim
            })
        
        env["csvViaHeaderOptions"] = sim["climate.csv-options"]
        #if soil_type == "poor_soil":
        #    limit_rootdepth()
        
        weather_file_name = station + "~" + climate + "_" + rcp + "_30" + "~lq~trans"
        weather_file_name += "-" + str(realization).zfill(2) + ".csv"

        #weather_file_name = station + "-" + climate
        #if climate != "now" and climate != "naw":
        #    weather_file_name += "-RCP85"
        #weather_file_name += "_" + str(realization).zfill(2) + ".csv"

        print (weather_file_name)

        if LOCAL_RUN:
            env["pathToClimateCSV"] = PATHS[USER]["LOCAL_ARCHIVE_PATH_TO_PROJECT"] + "no_snow_cover_assumed/" + weather_file_name
        else:
            env["pathToClimateCSV"] = PATHS[USER]["ARCHIVE_PATH_TO_PROJECT"] + "no_snow_cover_assumed/" + weather_file_name 
        
        env["customId"] = station + "|" + soil + "|" + rotation_id + "|" + climate + "|" + rcp + "|" + str(realization).zfill(2)

        socket.send_json(env)
        print(("sent env ", counter, " customId: ", env["customId"]))
        return counter + 1

    for station, soils in station2soil.items():
        print("station:", station)
        for soil in soils:
            print("soil:", soil)
            for rotation_id in rotations:
                for climate in climate_data:
                    for rcp in rcps:
                         for realization in range(1, 21):
                            counter = generate_and_send_env(station, soil, rotation_id, climate, rcp, realization, counter)
                         

    stop_store = time.perf_counter

    print(("sending ", (counter-1), " envs took ", (stop_store - start_store), " seconds"))
    return


main()