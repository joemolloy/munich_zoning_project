import os
import ConfigParser
import numpy as np

def load_config(filename):
    Config = ConfigParser.ConfigParser(allow_no_value=True)
    if not os.path.exists(filename):
        raise IOError("Config file %s does not exist" % filename)
    else:
        Config.read(filename)
        return Config

class LandUseConfig:
    def __init__(self, filename):
        self.config = load_config(filename)
        self.class_field = self.config.get("Class Field", "Field")
        self.resolution = self.config.getint("Input", "desired_raster_resolution")
        self.shapefiles = self.config.get("Input", "folder")
        self.mapping = [self.config.get("Class Values", c) for c in self.config.options("Class Values")]
        self.scale_factors = load_scaling_factors(self.config)
        self.encodings = {c : i+1 for (i,c) in enumerate(self.config.options("Class Values"))}
        self.translations = [(c, self.config.get("Class Values", c)) for c in self.config.options("Class Values")]

        #TODO: check all inputs

def load_scaling_factors(config):
    factors = {}
    for key in config.options("Scaling Factors"):
        try:
            values_strs = config.get("Scaling Factors", key).split(",")
            values = map(float,values_strs)
            assert np.isclose(sum(values),1.0), "Scaling factors must sum to 1.0"
            factors[key] = values
        except:
            raise Exception("Please provide valid scaling factors that add to 1.0, ie: '0.2,0.2,0.2,0.2'")
    return factors
