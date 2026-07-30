import sys, logging,os
from time import time, sleep, strftime
from PyQt5 import QtGui,QtCore
import PyQt5.QtWidgets as qw 
import pyqtgraph as pg
# import numpy as np

from TubeFurnaceInstruments import PressureGauge, MFCControl, FurnaceControl
from TubeFurnaceParams import ProcessParams, OtherParams
from ControlThreads import LoggingThread, ProcessThread, FillProcessThread, TempLoggingPlot, BasicLoggingPlot, FlowLoggingPlot,CurrentProcessPlot,BoxedPlot
from plot_tube_furnace_log import plot_log_file

class MainControlWindow(qw.QMainWindow):
    def __init__(self, logger, save_path, testing = False):
        super().__init__()
        self.testing = testing
        self.logger = logger
        self.save_path = save_path
        self.setWindowTitle('Control Panel')

        self.loggingOn = False

        self.resize(1280,720) # non-maximized state

        if self.testing == False:
            self.showMaximized()

        self.initUI()
       
        self.initThreads()

        ### connect GUI items made in initUI() to threads made in initThreads()
                ## make logging button a toggle?
        self.startLoggingButton.clicked.connect(self.startLogging)
        self.saveFigButton.clicked.connect(self.saveFig)
        self.fillButton.clicked.connect(self.runFillProcess)
        self.startProcessButton.clicked.connect(self.runAnnealProcess)
        self.abortProcessButton.clicked.connect(self.abortAll)
        # self.abortProcessButton.clicked.connect(self.ProcessThread.abort())
        self.delayInput.returnPressed.connect(self.updateLoggingDelay)
        self.programFurnaceButton.clicked.connect(self.programFurnace)

        self.show()

    def updateLoggingDelay(self):
        # self.delay = int(self.delayInput.text())
        self.delay = self.othertree.p.param('Logging Interval (s)').value()
        print(f'change logging interval to {self.delay}')

        self.LoggingThread.delay = self.delay

    def startLogging(self):
        # if self.startLoggingButton.isChecked
        if self.LoggingThread.running:
            self.LoggingThread.running = False
            print('pause logging')
        else:
            print('start logging')
            self.LoggingThread.start()

    def saveFig(self):
        print(self.save_path)
        if os.path.exists(self.save_path):
            plot_log_file(self.save_path)
        else:
            print("No data saved")

    def programFurnace(self):
        ## meant to program furnace without starting, if user wants to check
        furnace_params = []
        for si in range(1,len(self.tree.p.children())):
            # if self.tree.getValue(si,'Time') == 0:
            #     break
            furnace_params.append((self.tree.getValue(si,'Temperature'),self.tree.getValue(si,'Time')))
        self.Furnace.programFurnace(furnace_params)

    def initThreads(self):
        ## get params we need from tree:
        self.delay = self.othertree.p.param('Logging Interval (s)').value()
        self.overpressure_limit = self.othertree.p.param('Overpressure Limit (Torr)').value()
        self.ctrl_zone = self.othertree.p.param('Control Zone').value()

        self.MFC = MFCControl(logger=self.logger,testing=self.testing)
        self.PGauge = PressureGauge(logger=self.logger,testing=self.testing)
        self.Furnace = FurnaceControl(logger=self.logger,testing=self.testing)
        self.LoggingThread = LoggingThread(logger = self.logger, save_path = self.save_path, pgauge = self.PGauge, furnace = self.Furnace, mfc = self.MFC, overpressure = self.overpressure_limit)
        self.ProcessThread = ProcessThread(testing = self.testing, logger=self.logger, logthread = self.LoggingThread, pgauge = self.PGauge, furnace = self.Furnace, mfc = self.MFC,ptree = self.tree,ctrl_zone=self.ctrl_zone)
        self.FillThread = FillProcessThread(testing = self.testing, logger=self.logger, pgauge = self.PGauge, furnace = self.Furnace, mfc = self.MFC,tree = self.othertree)
        
        self.LoggingThread.overpressure_error.connect(self.ProcessThread.abort)
        self.LoggingThread.new_pressure_data.connect(self.pressurePlot.update)
        self.LoggingThread.new_temp_data.connect(self.tempPlot.update) 
        self.LoggingThread.new_flow_data.connect(self.flowPlot.update)
        # self.LoggingThread.new_Ar_data.connect(self.flowPlot.updateAr)
        # self.LoggingThread.new_H2S_data.connect(self.flowPlot.updateH2S)

    def runFillProcess(self):
        ''' This function initializes the current process plot then calls the fill process thread'''
        # if self.testing:
        #     print("Fill tube with Ar")
        #     print(self.othertree.getFillValue('Approach Pressure (Torr)'))
        try:
            ## disconnect other signals if conncted
            self.LoggingThread.new_temp_data.disconnect(self.currentProcessPlot.updateRightAxis)
            self.LoggingThread.new_flow_data.disconnect(self.currentProcessPlot.updateLeftAxis)
        except:
            pass
        ## get plot ready
        self.currentProcessPlot.plot.clear()
        self.currentProcessPlot.p2.clear()
        self.currentProcessPlot.plot.setLabel('left','Pressure',units='Torr')
        self.currentProcessPlot.plot.setLabel('right','Flow',units='sccm')
        self.currentProcessPlot.leftTrace = pg.PlotDataItem(pen=self.pressurePen,symbol='o',symbolBrush=pg.mkBrush(color=self.pressureColor))
        self.currentProcessPlot.plot.addItem(self.currentProcessPlot.leftTrace)
        self.currentProcessPlot.rightTrace = pg.PlotDataItem(pen=self.flowPen,symbol='o',symbolBrush=pg.mkBrush(color=self.arColor))
        self.currentProcessPlot.p2.addItem(self.currentProcessPlot.rightTrace)
        self.FillThread.message.connect(self.currentProcessPlot.message.setText)
        self.FillThread.new_pressure_data.connect(self.currentProcessPlot.updateLeftAxis)
        self.FillThread.new_Ar_data.connect(self.currentProcessPlot.updateRightAxis)
        self.FillThread.finished.connect(self.finishFillMessage)
        self.FillThread.start()

    def finishFillMessage(self):
        self.currentProcessPlot.message.setText('Finished fill process')

    def runAnnealProcess(self):
        try:
            self.FillThread.new_pressure_data.disconnect(self.currentProcessPlot.updateLeftAxis)
            self.FillThread.new_Ar_data.disconnect(self.currentProcessPlot.updateRightAxis)
        except:
            pass

        self.currentProcessPlot.plot.clear()
        self.currentProcessPlot.p2.clear()
        self.currentProcessPlot.plot.setLabel('right','Temperature',units='C')
        self.currentProcessPlot.plot.setLabel('left','Flow',units='sccm')
        self.currentProcessPlot.rightTrace = pg.PlotDataItem(pen=self.tempPen,symbol='o',symbolBrush=pg.mkBrush(color=self.tempColor)) # have to name rightTrace
        self.currentProcessPlot.p2.addItem(self.currentProcessPlot.rightTrace)
        self.currentProcessPlot.ArTrace = pg.PlotDataItem(pen=pg.mkPen(color=self.arColor,width=3),symbol='o',symbolburhs=pg.mkBrush(color=self.arColor))
        self.currentProcessPlot.plot.addItem(self.currentProcessPlot.ArTrace)
        self.currentProcessPlot.H2STrace = pg.PlotDataItem(pen=pg.mkPen(color=self.h2sColor,width=3),symbol='o',symbolBrush=pg.mkBrush(color=self.h2sColor))
        self.currentProcessPlot.plot.addItem(self.currentProcessPlot.H2STrace)

        self.LoggingThread.new_temp_data.connect(self.currentProcessPlot.updateRightAxis)
        self.LoggingThread.new_flow_data.connect(self.currentProcessPlot.updateLeftAxis)
        self.ProcessThread.message.connect(self.currentProcessPlot.message.setText)
        self.ProcessThread.ctrl_zone = self.othertree.p.param('Control Zone').value()
        self.ProcessThread.start()
            

    def abortAll(self):
        if self.FillThread.running:
            self.FillThread.abort()
        if self.ProcessThread.running:
            self.ProcessThread.abort()

    def closeEvent(self,event):
        if self.testing:
            print("trying to close gracefully")
        else:
            self.logger.info(f'Closing serial connections and GUI window.')
            self.Furnace.connection.close_connection()
            self.MFC.connection.close_connection()
            self.PGauge.connection.close_connection()
        event.accept()

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

        self.tempPlot = TempLoggingPlot(self.othertree.p.param('Control Zone').value(),'Temperature','C',self.tempColor)
        # print('made temp plot')
        self.pressurePlot = BasicLoggingPlot('Pressure','Torr',self.pressureColor)
        # print('made pressure plot')
        self.flowPlot = FlowLoggingPlot('Flow','sccm',[self.arColor,self.h2sColor])
        # print('made flow plot')
        # self.currentProcessPlot = CurrentProcessPlot('Pressure','Torr',self.pressureColor,'Flow','sccm',self.arColor,['Ar'])
        self.currentProcessPlot = BoxedPlot('Current Process',)
        self.cp2 = None ## second trace on current process plot
        # print('made empty CP2')

        self.startLoggingButton = qw.QPushButton("Start Logging") ## in the future make this a toggle?
        self.startLoggingButton.setCheckable(True)
        self.saveFigButton = qw.QPushButton("Save Process Figure")
        self.fillButton = qw.QPushButton("Bring tube to atmospheric pressure")
        self.startProcessButton = qw.QPushButton("Start Anneal")
        self.abortProcessButton = qw.QPushButton("Abort Process")
        self.delayInputLabel = qw.QLabel('Logging Interval (s):')
        self.delayInput = qw.QLineEdit('10')
        self.delayInput.setValidator(QtGui.QIntValidator())
        self.programFurnaceButton = qw.QPushButton("Program Furnace")
        self.programFurnaceButton.setToolTip("Optional. Set furnace program without running.")

        self.othertree.log_interval_change.connect(self.updateLoggingDelay)



        ## grid layout adds as                     r c rs cs (last 2 are rowspan, colspan)
        layout.addWidget(self.tree,                0,0,5, 1)
        layout.addWidget(self.startProcessButton,  5,0,1, 1)
        layout.addWidget(self.programFurnaceButton,6,0,1, 1)
        layout.addWidget(self.currentProcessPlot,  7,0,6, 2)

        layout.addWidget(self.othertree,           0,1,3, 1)
        layout.addWidget(self.startLoggingButton,  3,1,1, 1)
        # layout.addWidget(self.delayInputLabel,   1,1,1, 1)
        # layout.addWidget(self.delayInput,        2,1,1, 1)
        layout.addWidget(self.saveFigButton,       4,1,1, 1)
        layout.addWidget(self.fillButton,          5,1,1, 1)
        layout.addWidget(self.abortProcessButton,  6,1,1, 1)

        layout.addWidget(self.tempPlot,            0,2,4, 1)
        layout.addWidget(self.pressurePlot,        4,2,5, 1)
        layout.addWidget(self.flowPlot,            9,2,4, 1)

        for r in range(12):
            layout.setRowStretch(r,1)

if __name__ == "__main__":
    timestr = strftime('%Y%m%d-%H%M%S')
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename=f'logs/TubeFurnaceGUI_{timestr}.log',level=logging.DEBUG)
    logger.addHandler(logging.NullHandler())
    app = qw.QApplication(sys.argv)
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet())
    except:
        pass

    window = MainControlWindow(logger = logger, save_path=f'./logs/TubeFurnaceGUI_{timestr}.csv', testing = True)    
    sys.exit(app.exec())
    
