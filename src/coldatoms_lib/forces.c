#include <forces.h>
#include <math.h>
#include <assert.h>
#include <stdio.h>

static double distance(const double *r, double delta)
{
	double dist = 0.0;
	for (int i = 0; i < 3; ++i) {
		dist += r[i] * r[i];
	}
	dist += delta;
	return sqrt(dist);
}

static void coulomb_force_chunked(const double *positions, double charge,
				  double dt,
				  int num_ptcls, double delta, double k,
				  double *forces);
static void coulomb_force_cleanup(const double *positions, double charge,
				  double dt,
				  int num_ptcls, double delta, double k,
				  double *forces);

void coulomb_force(const double *positions, double charge, double dt,
int num_ptcls,
		   double delta, double k, double *forces)
{
	coulomb_force_chunked(positions, charge, dt, num_ptcls, delta, k, forces);
	coulomb_force_cleanup(positions, charge, dt, num_ptcls, delta, k, forces);
}

void coulomb_force_per_particle_charges(const double *positions,
					const double *charge, double dt, int num_ptcls,
					double delta, double k, double *forces)
{
	const double *r0 = positions;
	for (int i = 0; i < num_ptcls; ++i) {
		const double *r1 = positions;
		for (int j = 0; j < num_ptcls; ++j) {
			double r[3];
			for (int m = 0; m < 3; ++m) {
				r[m] = r0[m] - r1[m];
			}
			double dist = distance(r, delta);
			double dist_cubed = dist * dist * dist;
			double kp = dt * k * charge[i] * charge[j];
			for (int m = 0; m < 3; ++m) {
				forces[m] += kp * r[m] / dist_cubed;
			}
			r1 += 3;
		}
		r0 += 3;
		forces += 3;
	}
}

static void transpose(const double *restrict x, int m, int n,
		      double *restrict y)
{
	for (int i = 0; i < m; ++i) {
		for (int j = 0; j < n; ++j) {
			y[j * m + i] = x[i * n + j];
		}
	}
}

#define CHUNK_SIZE 32
#define NUM_COMPONENTS 3

static void distance_chunked(const double *restrict r, double delta, double
			     *restrict dist)
{
	for (int i = 0; i < CHUNK_SIZE; ++i) {
		dist[i] = delta;
	}
	for (int j = 0; j < NUM_COMPONENTS; ++j) {
		for (int i = 0; i < CHUNK_SIZE; ++i) {
			dist[i] += r[j * CHUNK_SIZE + i] *
			    r[j * CHUNK_SIZE + i];
		}
	}
	for (int i = 0; i < CHUNK_SIZE; ++i) {
		dist[i] = sqrt(dist[i]);
	}
}

static void accumulate_force(const double *restrict x0,
			     const double *restrict x1,
			     double *restrict f, double k, double delta)
{
	for (int i = 0; i < CHUNK_SIZE; ++i) {
		double r[NUM_COMPONENTS][CHUNK_SIZE];
		for (int m = 0; m < NUM_COMPONENTS; ++m) {
			for (int j = 0; j < CHUNK_SIZE; ++j) {
				r[m][j] =
				    x0[m * CHUNK_SIZE + i] -
				    x1[m * CHUNK_SIZE + j];
			}
		}

		double dist[CHUNK_SIZE];
		distance_chunked(&r[0][0], delta, &dist[0]);
		for (int j = 0; j < CHUNK_SIZE; ++j) {
			dist[j] = dist[j] * dist[j] * dist[j];
		}

		for (int m = 0; m < NUM_COMPONENTS; ++m) {
			for (int j = 0; j < CHUNK_SIZE; ++j) {
				f[m * CHUNK_SIZE + i] += k * r[m][j] / dist[j];
			}
		}
	}
}

static void coulomb_force_chunked(const double *restrict positions,
				  double charge, double dt, int num_ptcls, double delta,
				  double k, double *restrict forces)
{
	int num_chunks = num_ptcls / CHUNK_SIZE;

	k *= dt * charge * charge;

	for (int i = 0; i < num_chunks; ++i) {
		double x0[NUM_COMPONENTS][CHUNK_SIZE];
		transpose(positions + i * NUM_COMPONENTS * CHUNK_SIZE,
			  CHUNK_SIZE, NUM_COMPONENTS, &x0[0][0]);
		double f[NUM_COMPONENTS][CHUNK_SIZE] = { {0.0} };
		for (int j = 0; j < num_chunks; ++j) {
			double x1[NUM_COMPONENTS][CHUNK_SIZE];
			transpose(positions + j * NUM_COMPONENTS * CHUNK_SIZE,
				  CHUNK_SIZE, NUM_COMPONENTS, &x1[0][0]);
			accumulate_force(&x0[0][0], &x1[0][0], &f[0][0], k,
					 delta);
		}
		transpose(&f[0][0], NUM_COMPONENTS, CHUNK_SIZE,
			  forces + i * NUM_COMPONENTS * CHUNK_SIZE);
	}
}

static void coulomb_force_cleanup(const double *restrict positions,
				  double charge, double dt, int num_ptcls, double delta,
				  double k, double *restrict forces)
{
	int num_chunks = num_ptcls / CHUNK_SIZE;
	int n0 = num_chunks * CHUNK_SIZE;
	k *= dt * charge * charge;
	const double *r0 = positions;

	// Right leftovers.
	for (int i = 0; i < n0; ++i) {
		for (int j = n0; j < num_ptcls; ++j) {
			const double *r1 = positions + NUM_COMPONENTS * j;
			double r[NUM_COMPONENTS];
			for (int m = 0; m < NUM_COMPONENTS; ++m) {
				r[m] = r0[m] - r1[m];
			}
			double dist = distance(r, delta);
			double dist_cubed = dist * dist * dist;
			for (int m = 0; m < NUM_COMPONENTS; ++m) {
				forces[m] += k * r[m] / dist_cubed;
			}
		}
		r0 += NUM_COMPONENTS;
		forces += NUM_COMPONENTS;
	}

	// Bottom leftovers.
	for (int i = n0; i < num_ptcls; ++i) {
		for (int j = 0; j < num_ptcls; ++j) {
			const double *r1 = positions + j * NUM_COMPONENTS;
			double r[3];
			for (int m = 0; m < 3; ++m) {
				r[m] = r0[m] - r1[m];
			}
			double dist = distance(r, delta);
			double dist_cubed = dist * dist * dist;
			for (int m = 0; m < 3; ++m) {
				forces[m] += k * r[m] / dist_cubed;
			}
		}
		r0 += NUM_COMPONENTS;
		forces += NUM_COMPONENTS;
	}
}