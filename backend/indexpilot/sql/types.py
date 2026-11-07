"""Fixed PostgreSQL built-in type identities supported by the initial engine."""

BUILTIN_TYPE_OIDS = {
    "bool": 16,
    "int8": 20,
    "int2": 21,
    "int4": 23,
    "text": 25,
    "float4": 700,
    "float8": 701,
    "varchar": 1043,
    "date": 1082,
    "timestamp": 1114,
    "timestamptz": 1184,
    "numeric": 1700,
}
