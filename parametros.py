import json
import os

#apertura del json tipo de fluido
_carpeta=os.path.dirname(os.path.abspath(__file__))
_tipo_leche= os.path.join(_carpeta,"tipoLeche.json")

try:
    with open(_tipo_leche,"r", encoding="utf-8") as f:
        tipo_milk= json.load(f)
except FileNotFoundError:
    raise FileNotFoundError(f"No se encontro el archivo {_tipo_leche}")
except json.JSONDecodeError as error:
    raise ValueError(f"Error en la sintaxis {error}")

#Tipo de leche a usar
leche_utilizada="leche entera"
fluido= tipo_milk(leche_utilizada)
densidad_leche=fluido["densidad"]
calor_especificoMilk=fluido["calor_especifico"]

#Parametros tanque de la leche
litros= 20 
potencia_max= 3000.0 
masa_milk= litros * densidad_leche 

#Parametros termicos
temp_amb=25.0 
delta=75.0 #diferencia que genera la resistencia
agua_fria_temp=2.0
calor_especificoMilk= 3930.0  
ua_enf= 150.0 #coeficiente de enfriamiento

#parametros para transferencia
UA= potencia_max/delta #UA es coeficiente de transferencia de calor 
K=1.0/UA #ganancia de la planta
tau=(masa_milk*calor_especificoMilk)/UA #constante de tiempo 
tiem_muerto = 7.0 #tiempo de retardo sensor

#bacterias iniciales 
inicial_n=1e6 #bacterias iniciales

#importacion del json
_datos=os.path.dirname(os.path.abspath(__file__))
_datosjson= os.path.join(_datos,"pasteurizacion_metodos.json")
try:
    with open(_datosjson, "r", encoding="utf-8") as archivo:
        METODOS = json.load(archivo)
except FileNotFoundError:
    print(f"No se encontro el archivo {_datosjson}")
except json.JSONDecodeError as error:
    raise ValueError(f"Error en la sintaxis {error}")

def calculoPID(metodo="LTLT"):

    kp_base= 1.2*tau/(K*tiem_muerto*potencia_max) #ganancia 
    ti= 2.0*tiem_muerto#tiempo integral
    td= 0.5*tiem_muerto #tiempo derivativa
    ki_base = kp_base/ti;
    kd_base= kp_base*td;

    #multiplicacion
    ajustes={
        "LTLT":(1.0,1.0,1.0),
        "HTST":(1.5,1.2,1.0),
        "UHT":(2.0,1.5,0.8)
    }

    fp,fi,fd=ajustes.get(metodo, (1.0,1.0,1.0))
    return kp_base*fp, ki_base*fi, kd_base*fd