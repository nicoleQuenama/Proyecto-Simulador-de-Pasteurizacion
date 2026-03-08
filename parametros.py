import json
import os

#PARAMETROS
litros= 20 
densidad_leche= 1.030 
masa_milk= litros * densidad_leche 
calor_especificoMilk= 3930.0  
potencia_max= 3000.0 
temp_amb=25.0 
delta=75.0 

#enfriamiento
temp_enf= 4.0
ua_enf= 150.0
agua_fria_temp=2.0

#FUNCION DE TRANSFERENCIA
#formula para sacar UA
UA= potencia_max/delta #UA es coeficiente de transferencia de calor 
K=potencia_max/(UA*100) 
tau=(masa_milk*calor_especificoMilk)/UA #
tiem_muerto = 7.0 

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
    kp= 1.2*tau/(K*tiem_muerto)
    ki= kp/(2.0*tiem_muerto)
    kd= kp*0.5*tiem_muerto
    
    if metodo == "HTST":
        kphtst=kp *1.5
        kpihtst=ki*1.2
        return kphtst, kpihtst, kd
    elif metodo =="UHT":
        kpuhtt= kp*2.0
        kpiuht=ki*1.5
        kduht=kd*0.8
        return kpuhtt, kpiuht, kduht
    else:
        return kp, ki, kd