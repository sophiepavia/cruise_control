import numpy as np
import matplotlib.pyplot as plt
from math import pi, sin, copysign
import control as ct

#### CONTROLLER DYNAMICS MODELING ####
def vehicle_update(t, x, u, params={}):
    """"
    Vehicle Dynamics

    Parameters:
    x (array) : System state, car velocity in m/s
    u (array) : System input, [throttle, gear, road_slope], 
            where throttle is a float between 0 and 1, gear is an 
            integer between 1 and 5, and road_slope is in rad.
    Returns:
    dv (float) : Vehicle acceleration

    """
    # Get system parameters
    m = params.get('m', 1000.)              # vehicle mass, kg
    g = params.get('g', 9.8)                # gravitational constant, m/s^2
    k = params.get('k', 0.01)               # coefficient of friction
    alpha = params.get(
        'alpha', [40, 25, 16, 12, 10])      # gear ratio / wheel radius

    # Define variables for vehicle state and inputs
    v = x[0]                           # vehicle velocity
    throttle = np.clip(u[0], 0, 1)     # vehicle throttle
    gear = u[1]                        # vehicle gear
    theta = u[2]                       # road slope

    # Force generated by the engine
    omega = alpha[int(gear)-1] * v      # engine angular speed
    F = alpha[int(gear)-1] * motor_torque(omega, params) * throttle

    # Disturbance force 
    # Letting the grade of the road be theta, gravity gives the
    # force Fg = m*g*sin(theta)
    Fg = m * g * sin(theta)

    # Friction is Fr = m g k sgn(v), where k is
    # the coefficient of friction and sgn(v) is the sign of v (±1) or
    # zero if v = 0.
    sign = lambda x: copysign(1, x)         # define the sign() function to model sgn(v)
    Fr  = m * g * k * sign(v)

    # Final acceleration on the car
    Fd = Fg + Fr
    dv = (F - Fd) / m

    return dv

def motor_torque(omega, params={}):
    # Set up the system parameters
    Tm = params.get('Tm', 190.)             # engine torque constant
    omega_m = params.get('omega_m', 420.)   # peak engine angular speed
    beta = params.get('beta', 0.4)          # peak engine rolloff

    return np.clip(Tm * (1 - beta * (omega/omega_m - 1)**2), 0, None)

#### SIMUALTION PLOTTING ####
def simulate_plot(sys, t, y, label=None, t_hill=None, vref=20, linetype='g-', 
                    subplots=None, legend=None):
    """"
    Simulation plot creation

    Parameters:
    sys (ct.Interconnected sysyem) : Interconnection of a set of 
            input/output systems
    t (array) : time values of output from ct.input_output_response
    y (array) : response of the system from ct.input_output_response
    t_hill (int): time at which hill occurs
    vref (int): reference velocity 
    linetype (string): line type for pyplots
    subplots (array): plt.subplot(s)
    legend (bool): true or false for legend apperance 

    Returns:
    subplot_axes (array) : plt.subplots(s)

    """
    # set plot bounds based on velocity and throttle
    v_min = vref-1.2; v_max = vref+0.5; v_ind = sys.find_output('v')
    u_min = 0; u_max = 1; u_ind = sys.find_output('u')

    # fix bounds if needed based on sys response
    while max(y[v_ind]) > v_max: v_max += 1
    while min(y[v_ind]) < v_min: v_min -= 1

    # if no pre-exiting plot is passed in
    if subplots is None:
        subplots = [None, None]

    # array for return values
    subplot_axes = list(subplots)

    # velocity plot
    if subplot_axes[0] is None:
        # create subplot for half the area 
        subplot_axes[0] = plt.subplot(211)
    else:
        # inherit subplot axes
        plt.sca(subplots[0])
    # plot across t-values, velocity response
    plt.plot(t, y[v_ind], linetype)
    # plot vref as y = vref
    plt.plot(t, vref*np.ones(t.shape), 'k-')
    # if simulation encounters hill
    if t_hill:
        # plot reference line for time hill occurs
        plt.axvline(t_hill, color='k', linestyle='--', label='t hill')
    plt.axis([0, t[-1], v_min, v_max])
    plt.xlabel('Time $t$ [s]')
    plt.ylabel('Velocity $v$ [m/s]')
 
    # throttle plot
    if subplot_axes[1] is None:
        subplot_axes[1] = plt.subplot(2, 1, 2)
    else:
        # inherit subplot axes
        plt.sca(subplots[1])
    # plot across t-values, throttle response
    plt.plot(t, y[u_ind], linetype, label=label)
    # if simulation encounters hill 
    if t_hill:
        plt.axvline(t_hill, color='k', linestyle='--')
    if legend:
        plt.legend(frameon=False)
    plt.axis([0, t[-1], u_min, u_max])
    plt.xlabel('Time $t$ [s]')
    plt.ylabel('Throttle $u$')

    return subplot_axes

#### VEHICLE DECLARTION ####
# Define the input/output system for the vehicle
    # NonLinearIOSytem (note modeled this way for easy of use
    # actual system is a linear input/output system)
    # vechile_update: function that returns
    # the state update function for the vehicle
    # None: no function returns output as given state
    # inputs: throttle, gear, slope
    # outputs: updated velocity
    # state: velocity
    # dt: 0 (contiunous time system)
vehicle = ct.NonlinearIOSystem(
    vehicle_update, None, inputs=('u', 'gear', 'theta'), 
                outputs=('v'), states=('v'), dt=0, name='vehicle')

#### PI CONTROLLER ####
# my design of a controller to correct the discrepancy 
# between the desired reference signal and the measured
# output signal uses a combination of two terms: a proportional 
# term capturing the reaction to the current error, an integral 
# term capturing the reaction to the cumulative error

Kp = 0.5                        # proportional gain
Ki = 0.1                        # integral gain
controller = ct.tf2io(
    ct.TransferFunction([Kp, Ki], [1, 0.01*Ki/Kp]),
    name='control', inputs='u', outputs='y')

#connects vehicle I/O system and controller
cruise = ct.InterconnectedSystem(
    (vehicle, controller), name='cruise',
    connections = [('control.u', '-vehicle.v'), ('vehicle.u', 'control.y')],
    inplist = ('control.u', 'vehicle.gear', 'vehicle.theta'), inputs = ('vref', 'gear', 'theta'),
    outlist = ('vehicle.v', 'vehicle.u'), outputs = ('v', 'u'))

#### IMPLEMENTATION AND SIMULATION ####
# Define the time and input vectors
T = np.linspace(0, 25, 151)
vref = 20 * np.ones(T.shape)
gear = 4 * np.ones(T.shape)
theta0 = np.zeros(T.shape)

# Effect of a hill at t = 5 seconds
subplots = [None, None]
plt.figure()
plt.suptitle('Response to change in road slope')
theta_hill = np.array([
    0 if t <= 5 else
    4./180. * pi * (t-5) if t <= 6 else
    4./180. * pi for t in T])

# Plot the velocity response and find equillbrium
X0, U0 = ct.find_eqpt(
    cruise, [vref[0], 0], [vref[0], gear[0], theta_hill[0]],
    iu=[1, 2], y0=[vref[0], 0], iy=[0])

t, y = ct.input_output_response(cruise, T, [vref, gear, theta_hill], X0)

simulate_plot(cruise, t, y, t_hill=5, subplots=subplots)
plt.show()

#### TODO ####
# reponse in changes of mass within the car?
# other than PI controller? 
# other forces against the car? 
