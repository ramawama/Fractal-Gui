import multiprocessing
import sys
import threading
from multiprocessing.managers import SharedMemoryManager

from PySide2.QtGui import QIntValidator
from PySide2.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QApplication
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QObject, Slot, Signal

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import wsl
from fractal import Mandelbrot


class FractalWindow(QWidget):
    def __init__(self, filename, app):
        super().__init__()
        self.app = app
        self.posX = None
        self.posY = None

        ui_loader = QUiLoader()
        ui_widget = ui_loader.load(filename, self)
        self.iterations = ui_widget.findChild(QLineEdit, "iterations")
        self.layout = ui_widget.findChild(QVBoxLayout, "layout")
        self.processes = ui_widget.findChild(QLineEdit, "processes")
        self.resolution_x = ui_widget.findChild(QLineEdit, "resolution_x")
        self.resolution_y = ui_widget.findChild(QLineEdit, "resolution_y")
        self.reset_button = ui_widget.findChild(QPushButton, "reset_button")
        self.status = ui_widget.findChild(QLabel, "status")

        self.canvas = FigureCanvas()
        self.figure = self.canvas.figure
        self.axes = self.figure.add_subplot(111)
        self.axes.axis('off') # Hide the axes
        self.axes.set_position([0, 0, 1, 1]) # Make the axes fill the figure
        self.canvas.mpl_connect('button_press_event', self.app.on_pick_event)
        self.canvas.mpl_connect('button_release_event', self.app.on_release)
        self.layout.addWidget(self.canvas)

        self.default_res = (self.resolution_x.text(), self.resolution_y.text())
        self.default_iters = self.iterations.text()
        self.default_procs = self.processes.text()
        self.default_axes = self.axes.get_xlim(), self.axes.get_ylim()

        self.resolution_x.setValidator(QIntValidator())
        self.resolution_y.setValidator(QIntValidator())
        self.iterations.setValidator(QIntValidator())
        self.processes.setValidator(QIntValidator())

        self.reset_button.clicked.connect(self.app.reset)
        self.resolution_x.editingFinished.connect(self.app.xres_editing)  # part of qlineedit funciton
        self.resolution_y.editingFinished.connect(self.app.yres_editing)  # part of qlineedit funciton
        self.iterations.editingFinished.connect(self.app.iterations_editing)  # part of qlineedit funciton
        self.processes.editingFinished.connect(self.app.processes_editing)  # part of qlineedit funciton

        ui_widget.show()

    @property
    def axes(self):
        return self._axes

    @axes.setter
    def axes(self, new_axes):
        self._axes = new_axes

    @property
    def canvas(self):
        return self._canvas

    @canvas.setter
    def canvas(self, new_canvas):
        self._canvas = new_canvas

    @property
    def figure(self):
        return self._figure

    @figure.setter
    def figure(self, new_figure):
        self._figure = new_figure

    @property
    def iterations(self):
        return self._iterations

    @iterations.setter
    def iterations(self, new_iterations):
        self._iterations = new_iterations

    @property
    def layout(self):
        return self._layout

    @layout.setter
    def layout(self, new_layout):
        self._layout = new_layout

    @property
    def processes(self):
        return self._processes

    @processes.setter
    def processes(self, new_processes):
        self._processes = new_processes

    @property
    def resolution_x(self):
        return self._resolution_x

    @resolution_x.setter
    def resolution_x(self, new_resolution_x):
        self._resolution_x = new_resolution_x

    @property
    def resolution_y(self):
        return self._resolution_y

    @resolution_y.setter
    def resolution_y(self, new_resolution_y):
        self._resolution_y = new_resolution_y

    @property
    def reset_button(self):
        return self._reset_button

    @reset_button.setter
    def reset_button(self, new_reset_button):
        self._reset_button = new_reset_button

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, new_status):
        self._status = new_status


class FractalApp(QObject):
    non_gui_signal = Signal(object)

    def __init__(self, filename):
        super().__init__()
        self.non_gui_process = None
        self._root_widget = FractalWindow(filename, self)
        self._fractal = Mandelbrot(int(self.root_widget.resolution_x.text()), int(self.root_widget.resolution_y.text()), int(self.root_widget.iterations.text()))
        self._image = None
        self._currproc = self.root_widget.processes.text()
        self.zoomedx = None
        self.zoomedy = None
        self.zoomed = False
        self.update_plot()

    def update_plot(self):
        self.root_widget.status.setText("Calculating set...")
        self.root_widget.status.repaint()
        self.non_gui_process = threading.Thread(target=self.non_gui_update)
        self.non_gui_process.start()

    def non_gui_update(self):
        if self.zoomed:
            minx = (self.zoomedx[0] / self.fractal.dimensions[0]) * (self.fractal.x_range[1] - self.fractal.x_range[0]) + \
                   self.fractal.x_range[0]
            maxx = (self.zoomedx[1] / self.fractal.dimensions[0]) * (self.fractal.x_range[1] - self.fractal.x_range[0]) + \
                   self.fractal.x_range[0]
            miny = (1 - self.zoomedy[1] / self.fractal.dimensions[1]) * (self.fractal.y_range[1] - self.fractal.y_range[0]) + \
                   self.fractal.y_range[0]
            maxy = (1 - self.zoomedy[0] / self.fractal.dimensions[1]) * (self.fractal.y_range[1] - self.fractal.y_range[0]) + \
                   self.fractal.y_range[0]
            self.fractal.x_range = (minx, maxx)
            self.fractal.y_range = (miny, maxy)
        smm = SharedMemoryManager()
        smm.start()
        processes = []
        tasks, data = self.fractal.generate_tasks(smm, int(self.root_widget.processes.text()))
        for task in tasks:
            process = multiprocessing.Process(target=task)
            processes.append(process)
            process.start()
        [process.join() for process in processes]

        extent = [0, int(self.root_widget.default_res[0]), 0, int(self.root_widget.default_res[1])]
        image = self.root_widget.axes.imshow(self.fractal.data_to_image_matrix(data), extent=extent)
        smm.shutdown()
        self.non_gui_signal.connect(self.connect_non_gui)
        self.non_gui_signal.emit([image])

    @Slot(object)
    def connect_non_gui(self, data):
        self._image = data
        self.root_widget.status.setText("")
        self.root_widget.canvas.draw()

    def on_pick_event(self, event):
        if event.button == 1: #left click
            (self.posX, self.posY) = event.xdata, event.ydata

    def on_release(self, event):
        if event.button == 1:
            if self.posX is not None and self.posY is not None and event.xdata is not None and event.ydata is not None:
                self.zoomedx = sorted((self.posX, event.xdata))
                self.zoomedy = sorted((self.posY, event.ydata))
                self.zoomed = True
                self.update_plot()

    @Slot()
    def reset(self):
        self.zoomed = False
        if self.fractal.dimensions[1] != int(self.root_widget.default_res[0]) \
                or self.fractal.dimensions[0] != int(self.root_widget.default_res[1]) \
                or self.root_widget.default_axes[0] != self.root_widget.axes.get_xlim() \
                or self.root_widget.default_axes[1] != self.root_widget.axes.get_ylim():
            self.root_widget.resolution_x.setText(self.root_widget.default_res[0])
            self.root_widget.resolution_y.setText(self.root_widget.default_res[1])
            self.root_widget.axes.set_xlim(0, int(self.root_widget.default_res[0]))
            self.root_widget.axes.set_ylim(0, int(self.root_widget.default_res[1]))
            self._fractal = Mandelbrot(int(self.root_widget.resolution_x.text()), int(self.root_widget.resolution_y.text()), int(self.root_widget.iterations.text()))

            self.update_plot()

        # self.root_widget.iterations.setText(self.root_widget.default_iters)
        # self.root_widget.processes.setText(self.root_widget.default_procs)
        # self._root_widget.axes.set_xlim(self._root_widget.default_x)
        # self._root_widget.axes.set_ylim(self._root_widget.default_y)
        # self.root_widget.processes.setFocus()
        # self.root_widget.processes.selectAll()

    @Slot()
    def iterations_editing(self):
        num = self.root_widget.iterations.text()
        if num != "":
            new_iters = int(num)
            self.root_widget.iterations.setText(str(new_iters))
        else:
            self.root_widget.iterations.setText(self.root_widget.default_iters)
        if self._fractal.iterations != int(self.root_widget.iterations.text()):
            self._fractal = Mandelbrot(int(self.root_widget.resolution_x.text()), int(self.root_widget.resolution_y.text()), int(self.root_widget.iterations.text()))
            self.root_widget.reset_button.setFocus()
            self.update_plot()

    @Slot()
    def processes_editing(self):
        num = self.root_widget.processes.text()
        if num != "":
            new_procs = int(num)
            self.root_widget.processes.setText(str(new_procs))
        else:
            self.root_widget.processes.setText(self.root_widget.default_procs)
        if self._currproc != num: # if curr and new are diff update
            self._currproc = num
            self._fractal = Mandelbrot(int(self.root_widget.resolution_x.text()), int(self.root_widget.resolution_y.text()), int(self.root_widget.iterations.text()))
            self.root_widget.resolution_x.setFocus()
            self.root_widget.resolution_x.selectAll()
            self.update_plot()

    @Slot()
    def yres_editing(self):
        num = self.root_widget.resolution_y.text()
        if num != "":
            new_res = int(num)
            self.root_widget.resolution_y.setText(str(new_res))
        else:
            self.root_widget.resolution_y.setText(self.root_widget.default_res[1])
        if self.fractal.dimensions[1] != int(self.root_widget.resolution_y.text()): # if curr and new are diff update
            self._fractal = Mandelbrot(int(self.root_widget.resolution_x.text()), int(self.root_widget.resolution_y.text()), int(self.root_widget.iterations.text()))
            self.root_widget.iterations.setFocus()
            self.root_widget.iterations.selectAll()
            self.update_plot()

    @Slot()
    def xres_editing(self):
        num = self.root_widget.resolution_x.text()
        if num != "": #if the text box is not empty, ask carsten if we should acc for no input
            new_res = int(num)
            self.root_widget.resolution_x.setText(str(new_res))
        else:
            self.root_widget.resolution_x.setText(self.root_widget.default_res[0])
        if self.fractal.dimensions[0] != int(self.root_widget.resolution_x.text()): # if curr and new are diff update
            self._fractal = Mandelbrot(int(self.root_widget.resolution_x.text()), int(self.root_widget.resolution_y.text()), int(self.root_widget.iterations.text()))
            self.root_widget.resolution_y.setFocus()
            self.root_widget.resolution_y.selectAll()
            self.update_plot()

    @property
    def fractal(self):
        return self._fractal

    @property
    def image(self):
        return self.image

    @property
    def root_widget(self):
        return self._root_widget


def main():
    wsl.set_display_to_host()
    filename = "fracviz.ui"
    app = QApplication(sys.argv)

    q_app = FractalApp(filename)
    q_app.root_widget.show()

    sys.exit(app.exec_())


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
