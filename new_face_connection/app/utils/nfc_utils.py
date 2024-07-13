# app/utils/nfc_utils.py

from smartcard.util import toHexString

def get_card_info(connection, uid):
    # Intentar leer más información de la tarjeta (por ejemplo, tipo de tarjeta y bloques de memoria)
    try:
        # Leer el tipo de tarjeta
        apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        response, sw1, sw2 = connection.transmit(apdu)
        card_type = "Desconocido"
        if response:
            card_type = "MIFARE"  # Ejemplo simplificado, ajustar según tipo real

        # Leer los primeros bloques de memoria
        memory_data = {}
        for block in range(4):  # Leer los primeros 4 bloques como ejemplo
            apdu = [0xFF, 0xB0, 0x00, block, 0x10]  # Comando para leer un bloque
            response, sw1, sw2 = connection.transmit(apdu)
            if sw1 == 0x90 and sw2 == 0x00:
                memory_data[block] = toHexString(response)
            else:
                memory_data[block] = "No disponible"

        return {"UID": uid, "Tipo": card_type, "Memoria": memory_data}

    except Exception as e:
        return {"UID": uid, "Error": str(e)}
