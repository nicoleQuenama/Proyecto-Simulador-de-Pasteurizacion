import numpy as py;

#PARAMETROS
litros= 20 #cuanta leche vamos a pasteurizar en nuestro simulador de tanque
densidad_leche= 1.030 #densidad de la leche en g/ml
masa_milk= litros * densidad_leche 
calor_especificoMilk= 3930.0  
potencia_max= 3000.0 #simula la resistencia que calienta la leche  
temp_amb=25.0 #tope de temperatura donde la leche sigue estando en temperatura ambiente
delta=75.0 

#FUNCION DE TRANSFERENCIA
#formula para sacar UA
UA= potencia_max/delta #UA es coeficiente de transferencia de calor 
K=potencia_max/(UA*100) #sacamos cuanto aumenta la temperatura en %
t=(masa_milk*calor_especificoMilk)/UA #t es tau simbolo de ecuaciones diferencial de primer orden
tem_muerto = 7.0 #estimado, esto es theta y 7 porque lo estamos estimando, puede que no sea asi




