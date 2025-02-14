    #     new_temp_data = QtCore.pyqtSignal(object) ## type is a list [z1, z2, z3]
    #  def runFurnace(self):
    #     ## maybe a bit confusing, but run only tracks temp, doesn't start furnace
    #     self.running = True
    #     while self.running:
    #         new_data = self.getAllTemperatures()
    #         self.new_temp_data.emit(new_data)
    #         QtCore.QThread.msleep(self.delay*1000)

    # new_pressure_data = QtCore.pyqtSignal(float)
    # overpressure_error = QtCore.pyqtSignal(bool)
    # def runPGauge(self):
    #     self.running = True
    #     while self.running:
    #         measured_pressure = self.getPressure()
    #         self.new_pressure_data.emit(measured_pressure)
    #         if measured_pressure > self.overpressure_limit:
    #             self.overpressure_error.emit(True)
    #         QtCore.QThread.msleep(self.delay*1000)

    # new_Ar_data = QtCore.pyqtSignal(object)
    # new_H2S_data = QtCore.pyqtSignal(object)
    # def runMFC(self):
    #     ## normal running behavior reads sccm for active gases every [delay] seconds and sends to main
    #     self.running = True
    #     while self.running:
    #         Ar_sccm = self.get_data(self.gas_ids['Ar'])['sccm']
    #         H2S_sccm = self.get_data(self.gas_ids['H2S'])['sccm']
    #         self.new_Ar_data.emit(Ar_sccm)
    #         self.new_H2S_data.emit(H2S_sccm)
    #         QtCore.QThread.msleep(self.delay*1000)
import sys, logging
from time import time, sleep
from PyQt5 import QtGui,QtCore
import PyQt5.QtWidgets as qw 
import pyqtgraph as pg
import numpy as np

from TubeFurnaceInstruments import PressureGauge, MFCControl, FurnaceControl
from TubeFurnaceParams import ProcessParams, OtherParams

class LoggingThread(QtCore.QThread):

    overpressure_error = QtCore.pyqtSignal(bool)
    new_pressure_data = QtCore.pyqtSignal(object)
    new_temp_data = QtCore.pyqtSignal(object)
    new_Ar_data = QtCore.pyqtSignal(object)
    new_H2S_data = QtCore.pyqtSignal(object)

    def __init__(self, pgauge, furnace, mfc, overpressure = 800, delay = 30, testing = False):
        super().__init__()
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

            Ar_sccm = self.get_data(self.mfc.gas_ids['Ar'])['sccm']
            H2S_sccm = self.get_data(self.mfc.gas_ids['H2S'])['sccm']
            self.new_Ar_data.emit(Ar_sccm)
            self.new_H2S_data.emit(H2S_sccm)
            QtCore.QThread.msleep(self.delay*1000)

class ProcessThread(QtCore.QThread):

    def __init__(self, pgauge, mfc, furnace, ptree, delay = 30):
        super().__init__()
        self.PGauge = pgauge
        self.MFC = mfc
        self.Furnace = furnace
        self.delay = delay
        self.tree = ptree
        self.running = False


    def run(self):
        self.running = True
        while self.running:
            ## for programFurnace need to construct a list of tuples: (SP, TM)
            furnace_params = []
            for si in range(1,len(self.tree.p.children())):
                # if self.tree.getValue(si,'Time') == 0:
                #     break
                furnace_params.append((self.tree.getValue(si,'Temperature'),self.tree.getValue(si,'Time')))
            self.Furnace.programFurnace(furnace_params)

            ## start the furnace running the program defined above
            self.Furnace.startFurnace() 
            for si in range(1,len(self.tree.children())): ## TypeError: object of type 'builtin_function_or_method' has no len()
                ## Add condition to finish if segment is all zeros
                if self.tree.getValue(si,'Wait for') == 'Time':
                    self.MFC.set_sccm('Ar',int(self.tree.getValue(si,'Ar Flow')))
                    self.MFC.set_sccm('H2S',int(self.tree.getValue(si,'H2S Flow')))
                    sleep(int(self.tree.getValue(si,'Time')*60)) ## in minutes
                elif self.tree.getValue(si,'Wait for') == 'Temp':
                    self.MFC.set_sccm('Ar',int(self.tree.getValue(si,'Ar Flow')))
                    self.MFC.set_sccm('H2S',int(self.tree.getValue(si,'H2S Flow')))
                    self.waitForTemp(int(self.tree.getValue(si,'Temperature')))

    def waitForTemp(self, temperature, tolerance = 5):
        while True:
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
        self.running = False
        if self.timer is not None:
            print('stopping timer')
            self.timer.stop()


class MainControlWindow(qw.QMainWindow):
    def __init__(self, logger, testing = False):
        super().__init__()
        self.testing = testing
        self.logger = logger
        self.setWindowTitle('Control Panel')

        self.resize(1280,720) # non-maximized state

        if self.testing == False:
            self.showMaximized()

        self.initUI()
        self.delay = int(self.delayInput.text())
        self.initThreads()
        self.show()

    def updateDelay(self):
        # self.delay = int(self.delayInput.text())
        self.delay = self.othertree.p.param('Logging Interval (s)').value()
        print(f'change delay to {self.delay}')

        self.LoggingThread.delay = self.delay
        self.ProcessThread.delay = self.delay


    def initThreads(self):
        self.MFC = MFCControl(logger=self.logger,delay=self.delay,testing=self.testing)
        self.PGauge = PressureGauge(overpressure_limit=800,logger=self.logger,delay=self.delay,testing=self.testing)
        self.Furnace = FurnaceControl(logger=self.logger,delay=self.delay,testing=self.testing)
        self.LoggingThread = LoggingThread(pgauge = self.PGauge, furnace = self.Furnace, mfc = self.MFC, overpressure = self.overpressure_limit)
        self.ProcessThread = ProcessThread(pgauge = self.PGauge, furnace = self.Furnace, mfc = self.MFC,ptree = self.tree)
        
        self.LoggingThread.overpressure_error.connect(self.ProcessThread.abort)
        self.LoggingThread.new_pressure_data.connect(self.pressurePlot.update)
        self.LoggingThread.new_temp_data.connect(self.tempPlot.update) 
        self.LoggingThread.new_Ar_data.connect(self.flowPlot.updateAr)
        self.LoggingThread.new_H2S_data.connect(self.flowPlot.updateH2S)

    def initUI(self):
        ## Create an empty box to hold all the following widgets
        self.mainbox = qw.QWidget()
        self.setCentralWidget(self.mainbox)  # Put it in the center of the main window
        layout = qw.QGridLayout()  # All the widgets will be in a grid in the main box
        self.mainbox.setLayout(layout)  # set the layout\

        ## ~~ Colors ~~ ####
        self.pressurePen = pg.mkPen(color='#5DB4B7',width=2)
        self.flowPen = pg.mkPen(color='#DFC245',width=2)
        self.tempPen = pg.mkPen(color='#CC3300',width=3)

        self.h2sColor = '#DFC245'
        self.arColor = '#C1DE55'
        self.pressureColor = '#5DB4B7'
        self.tempColor = '#CC3300'

        ########################

        self.tree = ProcessParams()
        self.othertree = OtherParams()

        self.tempPlot = TempLoggingPlot('Temperature','C',self.tempColor)
        # print('made temp plot')
        self.pressurePlot = BasicLoggingPlot('Pressure','Torr',self.pressureColor)
        # print('made pressure plot')
        self.flowPlot = FlowLoggingPlot('Flow','sccm',self.arColor,self.h2sColor)
        # print('made flow plot')
        self.currentProcessPlot = pg.PlotWidget()
        # print('made empty CPP')
        self.cp2 = None ## second trace on current process plot
        # print('made empty CP2')

        self.startLoggingButton = qw.QPushButton("Start Logging") ## in the future make this a toggle?
        self.fillButton = qw.QPushButton("Bring tube to atmospheric pressure")
        self.startProcessButton = qw.QPushButton("Start Anneal")
        self.abortProcessButton = qw.QPushButton("Abort Process")
        self.delayInputLabel = qw.QLabel('Logging Interval (s):')
        self.delayInput = qw.QLineEdit('10')
        self.delayInput.setValidator(QtGui.QIntValidator())

        self.othertree.log_interval_change.connect(self.updateDelay)

        ## make logging button a toggle?
        self.startLoggingButton.clicked.connect(self.LoggingThread.start())
        self.fillButton.clicked.connect(self.fillTube)
        self.startProcessButton.clicked.connect(self.ProcessThread.start())
        self.abortProcessButton.clicked.connect(self.ProcessThread.abort())
        self.delayInput.returnPressed.connect(self.updateDelay)

        ## grid layout adds as                   r c rs cs (last 2 are rowspan, colspan)
        layout.addWidget(self.tree,              0,0,6, 1)
        layout.addWidget(self.currentProcessPlot,7,0,6, 2)

        layout.addWidget(self.othertree,         0,1,3, 1)
        layout.addWidget(self.startLoggingButton,3,1,1, 1)
        # layout.addWidget(self.delayInputLabel,   1,1,1, 1)
        # layout.addWidget(self.delayInput,        2,1,1, 1)
        layout.addWidget(self.startProcessButton,4,1,1, 1)
        layout.addWidget(self.fillButton,        5,1,1, 1)
        layout.addWidget(self.abortProcessButton,6,1,1, 1)

        layout.addWidget(self.tempPlot,          0,2,4, 1)
        layout.addWidget(self.pressurePlot,      4,2,5, 1)
        layout.addWidget(self.flowPlot,          9,2,4, 1)

        for r in range(12):
            layout.setRowStretch(r,1)

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
            trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color='{}{:02x}'.format(color, alpha),width=w))
            # print(f'made trace {zone} for temp logging plot')
            self.trace_list.append(trace)
        self.setLabel('left',ylabel,units=yunits,color=color)
    def update(self,new_data):
        # new data is a list of floats
        for i,trace in enumerate(self.trace_list):
            xdata,ydata = trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data[i])
            trace.setData(xdata,ydata)

class FlowLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,arColor,h2sColor,alpha = 200):
        super().__init__()
        self.getPlotItem().showGrid(x=True,y=True,alpha=0.5)
        self.addLegend()
        self.setLabel('left',ylabel,units=yunits,color=arColor)
        self.arTrace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color='{}{:02x}'.format(arColor, alpha),width=3),name='Ar')
        self.h2sTrace = self.plot(x=[time()],y=[0],pen=pg.mkPen(color='{}{:02x}'.format(h2sColor, alpha),width=3),name='H2S')
        

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





class BasicLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        # self.plot = pg.PlotWidget()
        self.getPlotItem().showGrid(x=True, y=True, alpha=1)
        self.trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color=color,width=2))
        # print('made trace on Basic Logging Plot')
        self.setLabel('left',ylabel,units=yunits,color=color)

    def update(self,new_data):
        xdata,ydata = self.trace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.trace.setData(x=xdata,y=ydata)

class LoggingPlot(qw.QWidget):
    def __init__(self, plot_title, color):
        super().__init__()
        masterLayout = qw.QVBoxLayout()
        self.pen = pg.mkPen(color, width=1.25)
        layout = qw.QVBoxLayout()
        self.group = qw.QGroupBox(plot_title)
        self.plot = pg.PlotWidget()
        for item in dataItems:
            self.trace_list.append(pg.PlotCurveItem(pen=self.pen)) ## what if I want different pens?
        self.plot.getPlotItem().showGrid(x=True, y=True, alpha=1)
        if "qdarkstyle" in sys.modules:
            self.plot.setBackground((25, 35, 45))

        self.group.setLayout(layout)
        layout.addWidget(self.plot)
        masterLayout.addWidget(self.group)

        self.setLayout(masterLayout)

    def update_plot(self,new_data):
        ## Let's say new_data is a tuple or a float
        if len(new_data) == 0:
            xdata,ydata = self.trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data)
            self.trace.setData(x=xdata, y=ydata)
        elif len(new_data) != len(self.plot.listDataItems()):
                return
        else:
            for trace in self.plot.listDataItems():
                color = trace.opts['pen'].color().name()
                (x_data, y_data) = trace.getData()
                xdata = np.append(xdata,time())
                ydata = np.append(ydata,new_data)
                trace.setData(x=xdata, y=ydata)
        # self.plot.getViewBox().autoRange()

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
    




