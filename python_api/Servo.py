#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#
"""Модуль для работы с сервоприводом Promobot по шине Modbus RTU."""

__author__ = "Promobot"
__license__ = "Apache License, Version 2.0"
__status__ = "Production"
__url__ = "https://git.promo-bot.ru"
__version__ = "0.1.0"


import modbus_io
import struct


#Servo registers
_TORQUE_REG         = 41
_SETPOINT_REG       = 42
_POS_REG            = 47
_SPEED_REG          = 48

_MODE_1_REG         = 3
_MODE_2_REG         = 4
_COMMAND_REG        = 40
_ERRORS_REG         = 45
_CURRENT_REG        = 49

_PID_SPEED_P_REG    = 10
_PID_SPEED_I_REG    = 12
_PID_SPEED_D_REG    = 14

_PID_POS_P_REG      = 16
_PID_POS_I_REG      = 18
_PID_POS_D_REG      = 20


#Allowed commands
_PASS_COMMANDS      = [0xDEAD,
                      0xAAAA]

#PID max and min values
_PID_MAX_VAL        = 20.0
_PID_MIN_VAL        = -0.01

#Errors list
_ERRORS_LIST        = ["COMMUNICATION",
                        "HALL_BOARD",
                        "WRONG_DIRECTION",
                        "OVERCURRENT",
                        "MAGNET_ERROR",
                        "ENCODER",
                        "DRV_ERR",
                        "DISABLED",
                        "REBOOTED"]


class Servo():
    """Класс для работы с сервоприводом.

    Args:
        * port (str): Имя последовательног порта шины данных, например ``/dev/RS485``.
        * slaveaddress (int): Адрес устройства. 1-250
        * baudrate (int): Скорость соединения. По умолчанию 460800 Бод
        * debug (bool): включение отладочного режима.
    
    """
    def __init__(self,port,address,baudrate = 460800,debug = False,ping = False):
        modbus_io.CLOSE_PORT_AFTER_EACH_CALL = True
        modbus_io.BAUDRATE = baudrate
        modbus_io.TIMEOUT = 0.1
        try:
            self.client = modbus_io.Instrument(port, address)
            self.client.debug = debug
        except Exception as e:   
            print('Cant init port:{0}  {1}'.format(port, e))                    
            exit()  
        if not ping:    
            self._init_settings()



    #######PRIVATE FUNCTIONS#######      
    def _write_register(self,
                        registeraddress,
                        value,
                        numberOfDecimals=0,
                        functioncode=6,
                        signed=True):
        try:
            self.client.write_register(registeraddress, value, numberOfDecimals, 6, signed)
            return True
        except Exception as e:
            print('ERROR! Servo:{0}  {1}'.format(self.client.address, e))
        return False




    def _write_registers(self,
                        registeraddress,
                        values):
        try:
            self.client.write_registers(registeraddress, values)
            return True
        except Exception as e:
            print('ERROR! Servo:{0}  {1}'.format(self.client.address, e))
        return False



    def _ping(self,
            registeraddress,
            numberOfRegisters,
            functioncode=3):
        
        return self.client.read_registers(registeraddress, numberOfRegisters, functioncode)
 


    def _read_registers(self,
                        registeraddress,
                        numberOfRegisters,
                        functioncode=3):
        try:
            return self.client.read_registers(registeraddress, numberOfRegisters, functioncode)
        except Exception as e:
            print('ERROR! Servo:{0}  {1}'.format(self.client.address, e))
        return False        


    def _bytes_to_float(self,high,low):
        raw = struct.pack('>HH',low,high)
        fl = struct.unpack('>f',raw)[0]
        return round(float(fl),2)


    def _float_to_bytes(self,value):
        val = float(value)
        ba = bytearray(struct.pack("f",val))
        vals = [0,0]
        vals[0] = ba[1] << 8 | ba[0]
        vals[1] = ba[3] << 8 | ba[2]
        return vals


    def _getSignedNumber(self,number, bitLength):
        mask = (2 ** bitLength) - 1
        if number & (1 << (bitLength - 1)):
            return number | ~mask
        else:
            return number & mask            
    

    def _read_errors(self,value):
        out_list = []
        error_list = bin(value)[2:].zfill(16)
        i = 0
        for e in reversed(error_list):
            if int(e) == 1:
                out_list.append(_ERRORS_LIST[i])
            i = i + 1
        return out_list


    def _check_PID_val(self,value):
        if value > _PID_MIN_VAL and value < _PID_MAX_VAL:
            return 1
        else:
            raise ValueError("Wrong value for PID register!")
            return 0  


    def _init_settings(self):
        mode = self._read_registers(_MODE_2_REG,1,3)
        if (mode is not False):
            mode[0] =  mode[0] & ~(1<<0)
            if (self._write_register(_MODE_2_REG,mode[0],signed=False) == 0):
                print('ERROR! Cant init servo:{0}'.format(self.client.address))
                return True 
            else:
                print('Servo:{0} Inited!'.format(self.client.address))
                return False    
        else:
            print('ERROR! Cant init servo:{0}'.format(self.client.address))
            return False        
    ############################    


    def custom_command(self,function,payload):
        """Отправка пользовательской команды Modbus RTU.

        Args:       
            * functioncode (int): код пользовательской функции. Например "запись в регистр" = 16.
            * payloadToSlave (bytearray): Данные для отправки (к этим данным автоматически будут добавлен адрес устройства и CRC)
        Returns:
            * ответ от устройства (string)
        Raises:
            ValueError

        """  
        out =  self.client._perform_custom_command(function,payload)
        out =  list(out)
        out[:] = [ord(x) for x in out]
        return out



    def set_torque(self,state):
        """Включение(отключение) питания обмоток двигателя

        Args:       
            * state (int): 
                | 0 - отключение питания обмоток двигателя, обмотки замкнуты, двигатель в торможении. 
                | 1 -Включение питания обмоток двигателя. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """         
        if state == 1 or state == 0:
            return self._write_register(_TORQUE_REG,state)
        else:
            raise ValueError("Wrong value for torque_register!") 


    def set_command(self,command):
        """Write command to servo.

        Args:
            * command (int): one of available commands. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """                 
        if command in _PASS_COMMANDS:
            return self._write_register(_COMMAND_REG,command,signed=False)
        else:
            raise ValueError("Wrong command for command_register!")


    def set_point(self,value):
        """Установка задачи. (Положение, скорость, ШИМ в зависимости от режима работы)

        Args:
            * value (int): Требуемое значение. от -32000 to 32000. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            None

        """            
        return self._write_register(_SETPOINT_REG,value,signed=True)


    def set_Pos_PID_P(self,value):
        """Запись коэф. P в ПИД регулятор по положению.

        Args:
            * value (int): Желаемое значение в диапазоне от 0.01 to 50.0. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """                   
        if (self._check_PID_val(value)):
            val = self._float_to_bytes(value)
            return self._write_registers(_PID_POS_P_REG,val)
                

    def set_Pos_PID_I(self,value):
        """Запись коэф. I в ПИД регулятор по положению.

        Args:
            * value (int): Желаемое значение в диапазоне от 0.01 to 50.0. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """                    
        if (self._check_PID_val(value)):
            val = self._float_to_bytes(value)
            return self._write_registers(_PID_POS_I_REG,val)            


    def set_Pos_PID_D(self,value):
        """Запись коэф. D в ПИД регулятор по положению.

        Args:
            * value (int): Желаемое значение в диапазоне от 0.01 to 50.0. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """           
        if (self._check_PID_val(value)):     
            val = self._float_to_bytes(value)
            return self._write_registers(_PID_POS_D_REG,val)    


    def set_Speed_PID_P(self,value):
        """Запись коэф. P в ПИД регулятор по скорости.

        Args:
            * value (int): Желаемое значение в диапазоне от 0.01 to 50.0. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """               
        if (self._check_PID_val(value)):     
            val = self._float_to_bytes(value)
            return self._write_registers(_PID_SPEED_P_REG,val)              


    def set_Speed_PID_I(self,value):
        """Запись коэф. I в ПИД регулятор по скорости.

        Args:
            * value (int): Желаемое значение в диапазоне от 0.01 to 50.0. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """                      
        if (self._check_PID_val(value)):     
            val = self._float_to_bytes(value)
            return self._write_registers(_PID_SPEED_I_REG,val)  


    def set_Speed_PID_D(self,value):
        """Запись коэф. D в ПИД регулятор по скорости.

        Args:
            * value (int): Желаемое значение в диапазоне от 0.01 to 50.0. 
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка
        Raises:
            ValueError

        """              
        if (self._check_PID_val(value)):     
            val = self._float_to_bytes(value)
            return self._write_registers(_PID_SPEED_D_REG,val)  


    def set_PID_Mode(self,value):
        """Высталвение режима работы ПИД регуляторов сервопривода.

        Args:
            * value (str): Режим работы.
                | "NORMAL" - каскадный режим ПИД ругялтора по скорости и положению.
                | "PWM" - отключение всех ПИД регуляторов и прямое управление скважностью ШИМ.
                | "SPEED" - включение только ПИД регулятора поп сокрости.                  
        Returns:
            * True если отправка команды прошла успешно
            * False если при отправке команды произошла ошибка

        Raises:
            ValueError

        """  
        mode = self._read_registers(_MODE_1_REG,1,3)
        if value == "NORMAL":
            mode[0] =  mode[0] | (1<<1)
            mode[0] =  mode[0] | (1<<2)


        if value == "PWM":
            mode[0] =  mode[0] & ~(1<<1)
            mode[0] =  mode[0] & ~(1<<2)

    
        if value == "SPEED":
            mode[0] =  mode[0] | (1<<1)
            mode[0] =  mode[0] & ~(1<<2)

        return self._write_register(_MODE_1_REG,mode[0],signed=False)   

               
    def get_data(self):
        """Чтение данных с сервопривода

        Args:
            None
        Returns:
            * Словарь с ключами: 
                | "Torque", 
                | "Setpoint" 
                | "Position" 
                | "Speed" 
                | "Command" 
                | "Current" 
                | "Pos_PID_P" 
                | "Pos_PID_I" 
                | "Pos_PID_D" 
                | "Speed_PID_P" 
                | "Speed_PID_I" 
                | "Speed_PID_D" 
                | "Errors"
        Raises:
            None

        """          
        data = {}
        values = self._read_registers(0,50)
        if (values is not False):
        
            data["Torque"]          = values[_TORQUE_REG]
            data["Setpoint"]        = self._getSignedNumber(values[_SETPOINT_REG],16)
            data["Position"]        = self._getSignedNumber(values[_POS_REG],16)
            data["Speed"]           = self._getSignedNumber(values[_SPEED_REG],16)
            data["Command"]         = values[_COMMAND_REG]
            data["Current"]         = self._getSignedNumber(values[_CURRENT_REG],16)     
            data["Pos_PID_P"]       = self._bytes_to_float(values[_PID_POS_P_REG],values[_PID_POS_P_REG + 1])
            data["Pos_PID_I"]       = self._bytes_to_float(values[_PID_POS_I_REG],values[_PID_POS_I_REG + 1])    
            data["Pos_PID_D"]       = self._bytes_to_float(values[_PID_POS_D_REG],values[_PID_POS_D_REG + 1])    
            data["Speed_PID_P"]     = self._bytes_to_float(values[_PID_SPEED_P_REG],values[_PID_SPEED_P_REG + 1])    
            data["Speed_PID_I"]     = self._bytes_to_float(values[_PID_SPEED_I_REG],values[_PID_SPEED_I_REG + 1])    
            data["Speed_PID_D"]     = self._bytes_to_float(values[_PID_SPEED_D_REG],values[_PID_SPEED_D_REG + 1])
            data["Errors"]          = self._read_errors(values[_ERRORS_REG])
        
        return data                                             