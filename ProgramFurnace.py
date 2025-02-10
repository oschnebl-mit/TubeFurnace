# this cell programs the furnace but does not start it
furnace = tc.temperature_controller

setpoint1 = 300
setpoint2 = 300
setpoint3 = 25
time1 = 20 # ramp time
time2 = 55 # more than anneal time b/c I can always shut off later
time3 = 0 # hopefully this is off

for zone_number in (1,2,3):
    logger.info(f'Programming zone {zone_number}:\r')
    command = f'\x020{zone_number}010WWRD0229,01,{setpoint1:04X}\x03\r'
    response = furnace.ask(command)
    logger.info(f'Setting SP1 to {setpoint1}. . .{response}')
    command = f'\x020{zone_number}010WWRD0230,01,{time1:04X}\x03\r'
    response = furnace.ask(command)
    logger.info(f'Setting TM1 to {time1}. . .{response}')
    command = f'\x020{zone_number}010WWRD0231,01,{setpoint2:04X}\x03\r'
    response = furnace.ask(command)
    logger.info(f'Setting SP2 to {setpoint2}. . .{response}')
    command = f'\x020{zone_number}010WWRD0232,01,{time2:04X}\x03\r'
    response = furnace.ask(command)
    logger.info(f'Setting TM2 to {time2}. . .{response}')
    command = f'\x020{zone_number}010WWRD0233,01,{setpoint3:04X}\x03\r'
    response = furnace.ask(command)
    logger.info(f'Setting SP3 to {setpoint3}. . .{response}')
    command = f'\x020{zone_number}010WWRD0232,01,{time3:04X}\x03\r'
    response = furnace.ask(command)
    logger.info(f'Setting TM3 to {time3}. . .{response}')
