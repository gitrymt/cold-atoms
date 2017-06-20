import numpy as np


class Ensemble(object):
    """An ensemble of particles.

    All ensembles have particle positions and velocities. In addition, an
    ensemble may define ensemble properties and per particle properties."""

    def __init__(self, num_ptcls=1):
        self.x = np.zeros([num_ptcls, 3], dtype=np.float64)
        self.v = np.zeros([num_ptcls, 3], dtype=np.float64)
        self.ensemble_properties = {}
        self.particle_properties = {}

    def get_num_ptcls(self):
        return self.x.shape[0]

    num_ptcls = property(get_num_ptcls,
                         'The number of particles in the ensemble')

    def set_particle_property(self, key, prop):
        """Set a particle property.

        key -- The name under which the property is stored.
        prop -- An array of the per particle properties. The array should have
        layout (num_ptcls, ...), i.e. the leading dimension should match the
        number of particles currently in the ensemble. We store a copy of
        prop."""

        if prop.shape[0] != self.num_ptcls:
            raise RuntimeError(
                'Size of property array does not match number of particles.')
        self.particle_properties[key] = np.copy(prop)

    def resize(self, new_size):
        shape = list(self.x.shape)
        shape[0] = new_size
        self.x.resize(shape)
        self.v.resize(shape)
        for particle_prop in self.particle_properties:
            shape = [self.particle_properties[particle_prop].shape]
            shape[0] = new_size
            self.particle_properties[particle_prop].resize(shape)

    def delete(self, indices):
        """Delete a subset of particles.

        The particles will be deleted inplace, i.e. the ensemble is mutated.

        indices -- The indices of particles to delete.
        """
        self.x = np.delete(self.x, indices, 0)
        self.v = np.delete(self.v, indices, 0)
        for property in self.particle_properties:
            property = np.delete(property, indices, 0)


class Source(object):
    """A particle source."""

    def __init__(self):
        pass

    def num_ptcls_produced(self, dt):
        """The number of particles that will be produced.

        This gives the number of particles that will be generated by the next
        call to produce_ptcls. It is legal for a source to return different
        numbers of particles on consecutive calls to num_ptcls_produced. This
        is often the case for stochastic sources that produce a certain number
        of particles on average.

        dt -- The duration of the time interval for which to produce particles.
        """
        return 0

    def produce_ptcls(self, dt, start, end, ensemble):
        """Generate particles.

        The number of particles generated must match the result return by a
        call to num_ptcls_produced(). We can expect end - start ==
        num_ptcls_produced().

        dt -- The duration of the time interval for which to produce particles.
        To make start and end and dt consistent with one another this dt should
        be the same as the dt passed to num_ptcls_produced to obtain start and
        end.
        start -- First position in ensemble where particles will be inserted.
        end -- One past the last position in the ensemble where particles will
        be inserted.
        ensemble -- The ensemble into which to insert the particles."""
        pass


def produce_ptcls(dt, ensemble, sources=[]):
    """Insert particles produced by sources into the ensemble.

    dt -- Length of time interval for which to produce particles.
    ensemble -- The ensemble into which to insert the particles.
    sources -- The particle source. Should derive from Source.
    """

    num_new_ptcls = []
    tot_new_ptcls = 0
    for s in sources:
        num_new_ptcls.append(s.num_ptcls_produced(dt))
        tot_new_ptcls += num_new_ptcls[-1]

    start = ensemble.num_ptcls
    ensemble.resize(ensemble.num_ptcls + tot_new_ptcls)
    for i, s in enumerate(sources):
        s.produce_ptcls(dt, start, start + num_new_ptcls[i], ensemble)
        start += num_new_ptcls[i]


class Sink(object):
    """A particle sink.

    Conceptually, sinks are represented by surfaces that remove particles from
    an ensemble if they hit the surface."""

    def find_absorption_time(self, x, v, dt):
        """The time at which particles will be arbsorbed by the sink.

        This method returns the time interval after which particles starting at
        x and traveling with velocity vector v along a straight line will hit
        the sink surface. dt is the duration of the interval in which an
        absorption time is sought. If the particle will not hit the sink in
        interval dt the function should return an absorption time greater than
        dt.

        x -- Initial particle positions.
        v -- Particle velocities.
        dt -- Length of time interval.
        """
        return np.full(x.shape[0], 2.0 * dt)

    def record_absorption(self, ensemble, dt, absorption_times, absorption_indices):
        """This function gets called when this sink absorbs a particle.

        ensemble -- The ensemble with particles which are potentially absorbed by this sink.
        dt -- The time interval during which we are processing decay events.
        absorption_times -- The times at which particles may be absorbed.
        absorption_indices -- The indices of particles which are being absorbed by this sink.
        """
        pass


class SinkPlane(Sink):

    def __init__(self, point, normal):
        """Generate a sink that absorbs particles hitting a plane.

        point -- A point in the plane.
        normal -- A normal to the plane.
        """
        self.point = point
        self.normal = normal

    def find_absorption_time(self, x, v, dt):
        taus = np.empty(x.shape[0])

        for i in range(x.shape[0]):
            normal_velocity = self.normal.dot(v[i])
            if (normal_velocity == 0.0):
                taus[i] = 2.0 * dt
            else:
                taus[i] = self.normal.dot(self.point - x[i]) / normal_velocity

        return taus


def process_sink(dt, ensemble, sink):
    if sink == None:
        return
    absorption_times = sink.find_absorption_time(ensemble.x, ensemble.v, dt)
    absorption_indices = np.arange(ensemble.num_ptcls)[
        abs(absorption_times - 0.5 * dt) <= 0.5 * dt]
    sink.record_absorption(ensemble, dt, absorption_times, absorption_indices)
    ensemble.delete(absorption_indices)


def drift_kick(dt, ensemble, forces=[], sink=None):
    """Drift-Kick-Drift push of particles.

    dt --       Time step size.
    ensemble -- The ensemble to advance.
    forces --   Forces acting on the ensemble. Each entry in this list must have
                a method force(dt, ensemble, f) that adds the force integrated
                over dt to f.
    sink --     The particle sink.
    
    """
    if len(forces) == 0:
        process_sink(dt, ensemble, sink)
        ensemble.x += dt * ensemble.v
    else:
        process_sink(0.5 * dt, ensemble, sink)

        ensemble.x += 0.5 * dt * ensemble.v

        f = np.zeros_like(ensemble.v)
        for force in forces:
            force.force(dt, ensemble, f)

        m = 0.0
        if 'mass' in ensemble.ensemble_properties:
            m = ensemble.ensemble_properties['mass']
        elif 'mass' in ensemble.particle_properties:
            m = ensemble.particle_properties['mass']
        else:
            raise RuntimeError('To accelerate particles we need a mass ensemble or particle property')
        ensemble.v +=  f / m

        process_sink(0.5 * dt, ensemble, sink)

        ensemble.x += 0.5 * dt * ensemble.v

