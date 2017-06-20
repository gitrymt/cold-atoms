import numpy as np


class RadiationPressure(object):
    """The force experienced by level atoms undergoing resonance fluorescence.

    This class computes the radiation pressure force, both determinstic and
    fluctuating recoil components, on an atom driven by a monochromatic laser
    field. The class handles spatial variations in laser intensity and of the
    atomic transition frequency as in a Zeeman slower. The wavevector of the
    laser field is assumed constant. RadiationPressure does not deal with
    attenuation of the laser field and is therefore limited to optically thin
    samples.
    An important application of RadiationPressure is to the simulation of
    Doppler cooling of atoms by combining two red detuned lasers with opposite
    propagation directions. In the context of laser cooling we are limited to
    situations of low total saturation and we cannot handle sub-Doppler
    cooling.
    """

    def __init__(self, gamma, hbar_k, intensity, detuning):
        """Specification of a RadiationPressure object.

        gamma -- The atomic decay rate (2\pi / excited state lifetime).
        hbar_k -- Single photon recoil momentum.
        intensity -- The intensity (in units of the saturation intensity) as a
                     function of atomic position. This object must have a
                     method intensities that, when applied to the atomic
                     positions returns the intensities at the position of the
                     atoms.
        detuning -- The detuning of the atomic transition from the laser. Red
                    detuning is negative and blue detuning is positive. The
                    detuning is a function of atomic velocities and may depend
                    on their position. This function must be applicable to x
                    and v and it should return an array with the detuning
                    values.
        """
        self.gamma = gamma
        self.hbar_k = np.copy(hbar_k)
        self.intensity = intensity
        self.detuning = detuning

    def force(self, dt, ensemble, f):
        s_of_r = self.intensity.intensities(ensemble.x)
        deltas = self.detuning.detunings(ensemble.x, ensemble.v)

        # First we compute the expected numbers of scattered photons.
        nbars = dt * s_of_r * ((self.gamma / 2.0 / np.pi) *
                (self.gamma / 2.0)**2 /
                ((self.gamma / 2.0)**2 * (1.0 + 2.0 * s_of_r) +
                 deltas**2))

        # Then we compute the recoil momentum according to momentum diffusion.
        # We assume that each atom undergoes a random walk in 3D momentum space
        # with nbar steps and each step of length hbar k.
        recoil_momenta = np.random.normal(size=ensemble.x.shape)
        recoil_momenta *= np.sqrt(nbars[:, np.newaxis] / 3.0) * np.linalg.norm(self.hbar_k)
        f += nbars[:, np.newaxis] * self.hbar_k + recoil_momenta

