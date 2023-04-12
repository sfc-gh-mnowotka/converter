import streamlit as st
import numpy as np
from scipy import integrate
from matplotlib import pyplot as plt


def solve_lorenz(N=10, angle=0.0, max_time=4.0, sigma=10.0, beta=8.0 / 3,
    rho=28.0):
    fig = plt.figure()
    ax = fig.add_axes([0, 0, 1, 1], projection='3d')
    ax.axis('off')
    ax.set_xlim((-25, 25))
    ax.set_ylim((-35, 35))
    ax.set_zlim((5, 55))

    def lorenz_deriv(x_y_z, t0, sigma=sigma, beta=beta, rho=rho):
        """Compute the time-derivative of a Lorenz system."""
        x, y, z = x_y_z
        return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]
    np.random.seed(1)
    x0 = -15 + 30 * np.random.random((N, 3))
    t = np.linspace(0, max_time, int(250 * max_time))
    x_t = np.asarray([integrate.odeint(lorenz_deriv, x0i, t) for x0i in x0])
    colors = plt.cm.viridis(np.linspace(0, 1, N))
    for i in range(N):
        x, y, z = x_t[i, :, :].T
        lines = ax.plot(x, y, z, '-', c=colors[i])
        plt.setp(lines, linewidth=2)
    ax.view_init(30, angle)
    st.pyplot(fig)
    return t, x_t


angle = st.slider('angle:', min_value=0.0, max_value=360.0, step=0.1, value=0.0
    )
max_time = st.slider('max_time:', min_value=0.1, max_value=4.0, step=0.1,
    value=4.0)
N = st.slider('N:', min_value=0, max_value=50, step=1, value=10)
sigma = st.slider('sigma:', min_value=0.0, max_value=50.0, step=0.1, value=10.0
    )
rho = st.slider('rho:', min_value=0.0, max_value=50.0, step=0.1, value=28.0)
solve_lorenz(angle=angle, max_time=max_time, N=N, sigma=sigma, rho=rho)
