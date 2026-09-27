import math

phi = (1 + math.sqrt(5)) / 2
phi_inv = 1 / phi
delta_t0 = phi_inv
t_cumulative = 0.0
n = 0
MAX_STEPS = 1000

print(f"{'Step (n)':<10} {'Interval (dt_n)':<20} {'Cumulative (t_N)':<20}")
print("-" * 52)

while n < MAX_STEPS:
    dt_n = delta_t0 * (phi_inv ** n)
    if dt_n == 0.0:
        print(f"Underflow reached at n = {n}")
        break
        
    t_cumulative += dt_n
    
    if n < 10:
        print(f"{n:<10} {dt_n:<20.15f} {t_cumulative:<20.15f}")
    elif n == 10:
        print("... [steps suppressed for brevity] ...")
        
    if dt_n < 1e-16:
        print(
            f"Truncation threshold met at n = {n}, "
            f"final t = {t_cumulative:.15f}"
        )
        break
        
    n += 1
else:
    print(
        f"Maximum step bound reached at n = {MAX_STEPS}, "
        f"final t = {t_cumulative:.15f}"
    )
