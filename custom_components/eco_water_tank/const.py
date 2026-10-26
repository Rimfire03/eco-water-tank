"""Constants for Eco Water Tank."""

DOMAIN = "eco_water_tank"

CONF_MODEL = "model"  # key of models.MODELS, or models.CUSTOM
CONF_CAPACITY = "capacity"  # litres
CONF_SHAPE = "shape"  # models.SHAPE_RECT | models.SHAPE_ROUND (custom tank)
CONF_WIDTH = "width"  # cm, rectangular tank
CONF_LENGTH = "length"
CONF_DIAMETER = "diameter"  # cm, circular tank
CONF_HEIGHT = "height"
CONF_LEVEL = "level_entity"
CONF_INLET = "inlet_entity"
CONF_OUTLET = "outlet_entity"
CONF_PUMP_LIMIT = "pump_limit"  # L left in the tank when the pump can no longer draw
CONF_RAIN = "rain_entity"  # cumulative rain gauge (mm)
CONF_AREA = "catchment_area"  # m²
CONF_EFFICIENCY = "efficiency"  # % of rain that reaches the tank
