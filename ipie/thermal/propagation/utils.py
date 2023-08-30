"""Routines for performing propagation of a walker"""

from ipie.thermal.propagation.continuous import Continuous
from ipie.thermal.propagation.planewave import PlaneWave


def get_propagator(options, qmc, system, hamiltonian, trial, verbose=False, lowrank=False):
    """Wrapper to select propagator class.

    Parameters
    ----------
    options : dict
        Propagator input options.
    qmc : :class:`pie.qmc.QMCOpts` class
        Trial wavefunction input options.
    system : class
        System class.
    trial : class
        Trial wavefunction object.

    Returns
    -------
    propagator : class or None
        Propagator object.
    """
    if hamiltonian.name == "UEG":
        propagator = PlaneWave(
            system,
            hamiltonian,
            trial,
            qmc,
            options=options,
            verbose=verbose,
            lowrank=lowrank,
        )
    else:
        propagator = Continuous(
            options,
            qmc,
            system,
            hamiltonian,
            trial,
            verbose=verbose,
            lowrank=lowrank,
        )

    return propagator
