from datetime import datetime, timezone

def timestamp_now():
    return int(datetime.now(timezone.utc).timestamp())

def convertValue(value):
    valueType = type(value)
    if valueType == float:
        return int(value)
    return value

def serialize_fields(fields):
    result = []
    for key in fields:
        result.append({
            "name": key,
            "value": convertValue(fields[key]),
        })
    return result

def create_increment_list(A, B, C):
    """
    Membuat daftar angka dari A sampai B dengan penambahan sebesar C.

    Args:
        A (float): Angka pertama (mulai).
        B (float): Angka terakhir (selesai).
        C (float): Angka penambahan (increment).

    Returns:
        list: Daftar angka yang dihasilkan.
    """
    if C == 0:
        return [A] if A <= B else []
    num_steps = int(round((B - A) / C)) + 1
    precision = len(str(C).split('.')[-1]) if '.' in str(C) else 0
    result = [round(A + i * C, precision) for i in range(num_steps)]
    return result
