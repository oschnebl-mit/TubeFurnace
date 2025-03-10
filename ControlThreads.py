
import sys, logging
from time import time, sleep
from PyQt5 import QtGui,QtCore
import PyQt5.QtWidgets as qw 
import pyqtgraph as pg
import numpy as np

from TubeFurnaceInstruments import PressureGauge, MFCControl, FurnaceControl
from TubeFurnaceParams import ProcessParams, OtherParams

class LoggingThread(QtCore.QThread):
    ''' Periodically asks for data from pressure gauge, furnace, and MFCS. Passes measured data and overpressure alarm to main window'''
    overpressure_error = QtCore.pyqtSignal(bool)
    new_pressure_data = QtCore.pyqtSignal(object)
    new_temp_data = QtCore.pyqtSignal(list)
    # new_Ar_data = QtCore.pyqtSignal(object)
    # new_H2S_data = QtCore.pyqtSignal(object)
    new_flow_data = QtCore.pyqtSignal(list)

    def __init__(self,logger, pgauge, furnace, mfc, overpressure = 800, delay = 30):
        super().__init__()
        self.logger = logger
        self.overpressure_limit = overpressure
        self.running = False
        self.delay = delay
        self.pgauge = pgauge
        self.furnace = furnace
        self.mfc = mfc

    def run(self):
        self.running = True
        while self.running:
            measured_pressure = self.pgauge.getPressure()
            self.new_pressure_data.emit(measured_pressure)
            if measured_pressure > self.overpressure_limit:
                self.overpressure_error.emit(True)

            measured_temps = self.furnace.getAllTemperatures()
            self.new_temp_data.emit(measured_temps)

            Ar_sccm = self.mfc.get_data(self.mfc.gas_ids['Ar'])['sccm']
            H2S_sccm = self.mfc.get_data(self.mfc.gas_ids['H2S'])['sccm']
            # self.new_Ar_data.emit(Ar_sccm)
            # self.new_H2S_data.emit(H2S_sccm)
            self.new_flow_data.emit([Ar_sccm,H2S_sccm])
            QtCore.QThread.msleep(self.delay*1000)

class ProcessThread(QtCore.QThread):
    message = QtCore.pyqtSignal(object)
    ''' Thread that controls anneal process. Mostly sets up initial work, then lets logger populate data'''
    def __init__(self,logger, testing, pgauge, mfc, furnace, ptree, delay = 30):
        super().__init__()
        self.logger = logger
        self.testing = testing
        self.PGauge = pgauge
        self.MFC = mfc
        self.Furnace = furnace
        self.delay = delay
        self.tree = ptree
        self.running = False


    def run(self):
        self.running = True
        self.message.emit('Programming furnace')
        ## for programFurnace need to construct a list of tuples: (SP, TM)
        furnace_params = []
        for si in range(1,len(self.tree.p.children())):
            # if self.tree.getValue(si,'Time') == 0:
            #     break
            furnace_params.append((self.tree.getValue(si,'Temperature'),self.tree.getValue(si,'Time')))
        self.Furnace.programFurnace(furnace_params)
        self.message.emit('Starting furnace')
        ## start the furnace running the program defined above
        self.Furnace.startFurnace() 
        for si in range(1,len(self.tree.children())): ## TypeError: object of type 'builtin_function_or_method' has no len()
            if not self.running:
                break ## figured out this is the best way to abort a thread
            ## Add condition to finish if segment is all zeros
            Ar_flow = int(self.tree.getValue(si,'Ar Flow'))
            H2S_flow = int(self.tree.getValue(si,'H2S Flow'))
            time = int(self.tree.getValue(si,'Time'))
            temperature = int(self.tree.getValue(si,'Temperature'))
            self.MFC.set_sccm('Ar',Ar_flow)
            self.MFC.set_sccm('H2S',H2S_flow)
            if self.tree.getValue(si,'Wait for') == 'Time':
                message = f'Setting Ar flow to {Ar_flow} and H2S flow to {H2S_flow} sccm. Waiting for {time} min'
                self.logger.info(message)
                self.message.emit(message)
                sleep(time*60) ## in minutes
            elif self.tree.getValue(si,'Wait for') == 'Temp':
                message = f'Setting Ar flow to {Ar_flow} and H2S flow to {H2S_flow} sccm. Waiting for {temperature} C.'
                self.logger.info(message)
                self.message.emit(message)
                self.waitForTemp(temperature)
        ## some way to shut things down when done
        # self.processFinished.emit()

    def waitForTemp(self, temperature, tolerance = 5):
        # while True:
        while self.running:
            currentTemp = self.Furnace.getAllTemperatures()[1] ## zone 2
            currentDelta = currentTemp - temperature
            if abs(currentDelta) < tolerance:
                break
            sleep(60)

    def abort(self):
        ''' Set furnace mode to reset and all gas flows to 0
        Nothing toggles so fine to run repeatedly
        Should this be in process thread?? '''
        self.Furnace.stopFurance() 
        self.MFC.stop_all_gas_flows()
        self.message.emit('Process aborted')
        self.running = False
        # if self.timer is not None:
        #     self.logger.info('Stopping timer')
        #     self.timer.stop()

class FillProcessThread(QtCore.QThread):
    ''' Thread that brings tube to atmospheric pressure. Does it's own measuring because
    the desired interval is so much shorter than a typical logging interval'''
    new_Ar_data = QtCore.pyqtSignal(object)
    new_pressure_data = QtCore.pyqtSignal(object)
    message = QtCore.pyqtSignal(object)

    def __init__(self, logger, testing, pgauge, mfc, furnace, tree, delay=1, abortPoints=3):
        super().__init__()
        self.logger = logger
        self.testing = testing
        self.PGauge = pgauge
        self.MFC = mfc
        self.Furnace = furnace
        self.delay = delay # delay in seconds
        self.tree = tree
        self.running = False
        self.abortPoints = abortPoints

    def abort(self):
        self.MFC.stop_all_gas_flows()
        self.MFC.set_sccm('Ar',0)
        self.message.emit('Process aborted')
        self.running=False
#         self.t0 = time()
        ## taking points causing issues for abort
#         for n in range(self.abortPoints): ## take a few data points so user can see flow has stopped
#             Ar_sccm = self.MFC.get_data(self.MFC.gas_ids['Ar'])['sccm']
           
#             self.new_Ar_data.emit([Ar_sccm,0])
#             self.new_pressure_data.emit(self.PGauge.getPressure())
#             sleep(self.delay)



    def run(self):
        self.running = True
        self.stopPressure = int(self.tree.getFillValue('Fill Pressure (Torr)'))
        self.approachPressure = int(self.tree.getFillValue('Approach Pressure (Torr)'))
        self.initFlow = self.tree.getFillValue('Approach Ar Flow (sccm)')
        self.finalFlow = self.tree.getFillValue('Fill Ar Flow (sccm)')
        self.t0 = time()

        if self.testing: ## putting a testing mode in this function because the instruments return constant values in testing mode
            dummy_pressure = 1
            dummy_flow = 0.1
        while self.running:
            if self.testing:
                actual_tube_pressure = dummy_pressure + dummy_flow/2 ## scaling to look realistic
                dummy_pressure = actual_tube_pressure
                Ar_sccm = dummy_flow
            else:
                actual_tube_pressure = self.PGauge.getPressure()
                Ar_sccm = self.MFC.get_data(self.MFC.gas_ids['Ar'])['sccm']
            tcurr = time()-self.t0
            if actual_tube_pressure >= self.stopPressure:
                self.MFC.set_sccm('Ar',0)
                message = f'Reached {self.stopPressure} Torr, stopping Ar flow'
                self.finished.emit()
                self.running = False
            elif actual_tube_pressure >= self.approachPressure:
                self.MFC.set_sccm('Ar',self.initFlow)
                if self.testing:
                    dummy_flow = int(self.initFlow)
            elif tcurr <= 5:
                self.MFC.set_sccm('Ar',self.initFlow)
                message = f'Setting Ar to initial flow: {self.initFlow} sccm'
                if self.testing:
                    dummy_flow = int(self.initFlow)
            elif tcurr > 5:
                self.MFC.set_sccm('Ar',self.finalFlow)
                message = f'Setting Ar to {self.finalFlow} sccm'
                if self.testing:
                    dummy_flow = int(self.finalFlow)
            self.logger.info(message)
            self.message.emit(message)
            self.new_Ar_data.emit([Ar_sccm])
            self.new_pressure_data.emit([actual_tube_pressure])
            sleep(self.delay)




class TempLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        self.getPlotItem().showGrid(x=True,y=True,alpha=0.5)
        self.trace_list = []
        for zone in (1,2,3):
            #  pen = pg.mkPen(color='{}{:02x}'.format(color, alpha), width=lw,connect="finite")
            if zone == 2:
                w = 4
                alpha = 250
            else:
                w = 3
                alpha = 100
            trace = pg.PlotCurveItem(pen=pg.mkPen(color='{}{:02x}'.format(color, alpha),width=w))
            self.addItem(trace)
            self.trace_list.append(trace)
        self.setLabel('left',ylabel,units=yunits,color=color)
        self.setAxisItems({'bottom':pg.DateAxisItem()})
    def update(self,new_data):
        # new data is a list of floats
        for i,trace in enumerate(self.trace_list):
            xdata,ydata = trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data[i])
            trace.setData(xdata,ydata)

class FlowLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,colors,alpha = 200):
        super().__init__()
        self.setAxisItems({'bottom':pg.DateAxisItem()})
        self.getPlotItem().showGrid(x=True,y=True,alpha=0.5)
        self.addLegend()
        self.setLabel('left',ylabel,units=yunits,color=colors[0])
        self.traceList = []
        for i,name in enumerate(['Ar','H2S']):
            trace = pg.PlotCurveItem(pen=pg.mkPen(color='{}{:02x}'.format(colors[i], alpha),width=3),name=name)
            self.traceList.append(trace)
            self.addItem(trace)# self.arTrace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color='{}{:02x}'.format(arColor, alpha),width=3),name='Ar')
            # self.h2sTrace = self.plot(x=[time()],y=[0],pen=pg.mkPen(color='{}{:02x}'.format(h2sColor, alpha),width=3),name='H2S')
        
    def update(self,new_data):
        if len(new_data) != len(self.listDataItems()):
            print(f'Gas data {new_data} does not match number of traces: {len(self.tracelist)}')
        for i, trace in enumerate(self.listDataItems()):
            xdata,ydata = trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data[i])
            trace.setData(x=xdata,y=ydata)

    def updateH2S(self,new_data):
        xdata,ydata = self.h2sTrace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.h2sTrace.setData(x=xdata,y=ydata)

    def updateAr(self,new_data):
        xdata,ydata = self.arTrace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.arTrace.setData(x=xdata,y=ydata)

class CurrentProcessPlot(pg.PlotWidget):
    ## initialize plot with left and right axes but no traces yet
    ## plot has functions to add data to left side and right side
    def __init__(self,leftLabel,leftUnits,leftColor,rightLabel,rightUnits,rightColor,rightTraceNames):
        super().__init__()
        self.setAxisItems({'bottom':pg.DateAxisItem()})
        self.getPlotItem().showGrid(x=True, y=True, alpha = 0.5)
        self.leftTrace = pg.PlotCurveItem(pen=pg.mkPen(color=leftColor,width=2))
        self.addItem(self.leftTrace)
#         self.leftTrace = self.plot(x=[time()],y=[0],pen = pg.mkPen(color=leftColor,width=2))

        self.setLabel('left',leftLabel,units=leftUnits,color=leftColor)
        # self.addItem(self.leftTrace)
        self.p2 = pg.ViewBox()
        self.showAxis('right')
        self.scene().addItem(self.p2)
        self.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self)
        self.setLabel('right',rightLabel,units=rightUnits,color=rightColor)
        self.updateViews()
        self.getViewBox().sigResized.connect(self.updateViews)
        self.rightTraceList = []

        self.rightLegend = pg.LegendItem()
        self.p2.addItem(self.rightLegend)


    def updateViews(self):
            self.p2.setGeometry(self.getViewBox().sceneBoundingRect())
            self.p2.linkedViewChanged(self.getViewBox(), self.p2.XAxis)

    def updateLeftAxis(self, new_left_data):
        print(f'Add to left axis: {new_left_data}')
        if len(new_left_data)==3:
            print(f'Add to left axis: {new_left_data[1]}')
            new_left_data = new_left_data[1]
        else:
            new_left_data = new_left_data[0]
        xdata,ydata = self.leftTrace.getData()
        xdata = np.append(xdata,time())
        # ydata = np.append(ydata,100)
        ydata = np.append(ydata,new_left_data)
        self.leftTrace.setData(x=xdata,y=ydata)
        # self.getViewBox().autoRange()

    def updateRightAxis(self,new_right_data):
        # new_right_data needs to be a list
        print(f'Add to right axis: {new_right_data}')
        for i,trace in enumerate(self.rightTraceList):
            xdata,ydata = trace.getData()
            # print(xdata,ydata) ## debugging
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_right_data[i])
            trace.setData(x=xdata,y=ydata)
        # self.p2.autoRange()


class BasicLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        # self.plot = pg.PlotWidget()
        self.setAxisItems({'bottom':pg.DateAxisItem()})
        self.getPlotItem().showGrid(x=True, y=True, alpha=0.5)
        # self.trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color=color,width=2))
        self.trace = pg.PlotCurveItem(pen=pg.mkPen(color=color,width=2))
        self.addItem(self.trace)
        # print('made trace on Basic Logging Plot')
        self.setLabel('left',ylabel,units=yunits,color=color)

    def update(self,new_data):
        xdata,ydata = self.trace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.trace.setData(x=xdata,y=ydata)

class BoxedPlot(qw.QWidget):
    def __init__(self, plot_title):
        super().__init__()
        masterLayout = qw.QVBoxLayout()
        # self.pen = pg.mkPen(color, width=2)

        layout = qw.QVBoxLayout()
        self.group = qw.QGroupBox(plot_title)
        self.plot = pg.PlotWidget()
        self.plot.getPlotItem().showGrid(x=True, y=True, alpha=0.5)
        self.plot.setAxisItems({'bottom':pg.DateAxisItem()})
        if "qdarkstyle" in sys.modules:
            self.plot.setBackground((25, 35, 45))
        self.group.setLayout(layout)
        self.message = qw.QLabel("Inactive")
        layout.addWidget(self.message)
        layout.addWidget(self.plot)
        masterLayout.addWidget(self.group)

        self.setLayout(masterLayout)
    
        self.p2 = pg.ViewBox()
        self.plot.showAxis('right')
        self.plot.scene().addItem(self.p2)
        self.plot.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.plot)
        # self.setLabel('right',rightLabel,units=rightUnits,color=rightColor)
        self.updateViews()
        self.plot.getViewBox().sigResized.connect(self.updateViews)

        self.Legend = pg.LegendItem()
        self.p2.addItem(self.Legend)

    def updateViews(self):
            self.p2.setGeometry(self.plot.getViewBox().sceneBoundingRect())
            self.p2.linkedViewChanged(self.plot.getViewBox(), self.p2.XAxis)

    def updateRightAxis(self, new_right_data):
        # print(f'Add to right axis: {new_right_data}')
        if len(new_right_data)==3:
            # print(f'Add to right axis: {new_right_data[1]}')
            new_right_data = new_right_data[1]
        else:
            new_right_data = new_right_data[0]
        xdata,ydata = self.rightTrace.getData()
        xdata = np.append(xdata,time())
        # ydata = np.append(ydata,100)
        ydata = np.append(ydata,new_right_data)
        self.rightTrace.setData(x=xdata,y=ydata)
        # self.getViewBox().autoRange()

    def updateLeftAxis(self,new_left_data):
        # new_right_data needs to be a list
        # print(f'Add to left axis: {new_left_data}')
        for i,trace in enumerate(self.plot.listDataItems()):
            xdata,ydata = trace.getData()
            # print(xdata,ydata) ## debugging
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_left_data[i])
            trace.setData(x=xdata,y=ydata)
        # self.p2.autoRange()
if __name__ == "__main__":

    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    app = qw.QApplication(sys.argv)
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet())
    except:
        pass

    window = MainControlWindow(logger = logger, testing = True)
    
    sys.exit(app.exec())
    




