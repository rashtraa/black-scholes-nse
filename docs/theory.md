# Theory behind the engine

This page explains the ideas each module implements. References are at the end.

## 1. Options and no-arbitrage

A call (put) gives the right to buy (sell) the share at strike K on the
expiry date. Its payoff is max(S_T - K, 0) for a call and max(K - S_T, 0)
for a put. No-arbitrage alone bounds European prices:

    max(S0 - D - K e^(-rT), 0)  <=  c  <=  S0 - D
    max(K e^(-rT) - S0 + D, 0)  <=  p  <=  K e^(-rT)

It also ties calls and puts together through **put-call parity**:

    c + D + K e^(-rT) = p + S0

Both portfolios pay max(S_T, K) at expiry, so they must cost the same today.
`model.no_arbitrage_bounds` implements the bounds. The analysis tests parity
on market prices.

## 2. The binomial tree: pricing without probabilities

Suppose that over one step the share moves up by a factor u or down by d.
Then a portfolio of Delta = (f_u - f_d)/(S0 u - S0 d) shares and one short
option is riskless, so it must earn r. That fixes the option price:

    f = e^(-r dt) [p f_u + (1 - p) f_d],     p = (e^(r dt) - d) / (u - d)

p is not the real-world probability of an up move. It is the probability
that makes the share earn r. With u = e^(sigma sqrt(dt)), d = 1/u
(Cox-Ross-Rubinstein) and many steps, the tree converges to the
Black-Scholes price. `binomial.py` implements this; the analysis uses it as
an independent check on the formula.

## 3. How share prices move

A symmetric random walk, sped up and scaled by 1/sqrt(n), converges by the
central limit theorem to **Brownian motion**, also called a Wiener process.
Its increments are independent and normal, with variance equal to elapsed
time. Share prices are modelled in percentage terms:

    dS = mu S dt + sigma S dz

**Itô's lemma** applied to G = ln S gives

    d(ln S) = (mu - sigma^2/2) dt + sigma dz

so ln S_T is normal and S_T is lognormal. The -sigma^2/2 term is
*volatility drag*: compound growth is below the average return.
`simulation.py` uses this exact solution to simulate S_T.

## 4. Black-Scholes-Merton

The option and the share are driven by the same dz. So a portfolio of one
short option and dc/dS shares is riskless over an instant, and must earn r.
Writing that down gives the Black-Scholes equation:

    dc/dt + r S dc/dS + (1/2) sigma^2 S^2 d^2c/dS^2 = r c

The expected return mu has dropped out, so options can be priced as if
investors were risk-neutral. With the payoff as boundary condition, the
solution is

    c = S0 N(d1) - K e^(-rT) N(d2)
    p = K e^(-rT) N(-d2) - S0 N(-d1)
    d1 = [ln(S0/K) + (r + sigma^2/2) T] / (sigma sqrt T),    d2 = d1 - sigma sqrt T

N(d2) is the risk-neutral probability that the call is exercised. S0 N(d1)
is today's value of the share you expect to receive, and K e^(-rT) N(d2) is
today's value of the strike you expect to pay. Known cash dividends enter by
replacing S0 with S0 - D, where D is their present value.

## 5. The normal distribution N(x)

N(x) has no closed form. `normal.py` uses the Abramowitz-Stegun polynomial
approximation (26.2.17):

    N(x) = 1 - N'(x) (a1 k + a2 k^2 + a3 k^3 + a4 k^4 + a5 k^5),   k = 1 / (1 + 0.2316419 x),   x >= 0

with N(-x) = 1 - N(x). The error is below 7.5e-8. The tests check it
against direct Simpson's-rule integration of the bell curve. Random normals
come from the **Box-Muller** transform: two uniforms u1, u2 give
z = sqrt(-2 ln u1) cos(2 pi u2).

## 6. The Greeks and delta hedging

The Greeks are the partial derivatives of the price:

| Greek | Call | Measures |
|---|---|---|
| Delta | N(d1) | change per Rs 1 move in S |
| Gamma | N'(d1) / (S sigma sqrt T) | change in delta per Rs 1 move |
| Theta | -S N'(d1) sigma / (2 sqrt T) - r K e^(-rT) N(d2) | change as time passes |
| Vega | S N'(d1) sqrt T | change per unit of sigma |
| Rho | K T e^(-rT) N(d2) | change per unit of r |

Delta hedging, holding Delta shares per option sold, is the practical form
of the riskless portfolio in section 4. With discrete rebalancing, the
hedged position earns approximately

    (1/2) Gamma S^2 (sigma_charged^2 - sigma_realised^2) dt

per step. So a seller who charged more volatility than was realised profits,
and vice versa. `hedging.py` tests this on real prices.

## 7. Volatility: historical and implied

sigma is the only input that cannot be observed. From history: compute
daily log returns u_i = ln(S_i / S_{i-1}), take their sample standard
deviation s, and annualise with sigma = s sqrt(252).

From the market: the **implied volatility** is the sigma at which the
model reproduces the market price. The price is strictly increasing in
sigma, so the answer is unique whenever the price lies inside the
no-arbitrage bounds. `implied_vol.py` finds it with Newton's method
(slope = vega) and falls back to bisection.

If Black-Scholes were exactly right, implied volatility would be the same
at every strike. In real markets it isn't (the volatility smile), which
is one of the project's findings.

## References

- Black, F. and Scholes, M. (1973). The Pricing of Options and Corporate Liabilities. *Journal of Political Economy*, 81(3), 637-654.
- Merton, R. C. (1973). Theory of Rational Option Pricing. *Bell Journal of Economics and Management Science*, 4(1), 141-183.
- Cox, J. C., Ross, S. A. and Rubinstein, M. (1979). Option Pricing: A Simplified Approach. *Journal of Financial Economics*, 7(3), 229-263.
- Hull, J. C. *Options, Futures, and Other Derivatives*. Pearson.
- Abramowitz, M. and Stegun, I. A. (1964). *Handbook of Mathematical Functions*, formula 26.2.17.
