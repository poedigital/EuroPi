# Comprehensive List of Mathematical Functions

## 1. Elementary Functions

### 1.1. Algebraic Functions
- **Constant function**: \( f(x) = c \)
- **Identity function**: \( f(x) = x \)
- **Linear function**: \( f(x) = ax + b \)
- **Quadratic function**: \( f(x) = ax^2 + bx + c \)
- **Cubic function**: \( f(x) = ax^3 + bx^2 + cx + d \)
- **Polynomial function**: \( f(x) = a_n x^n + a_{n-1} x^{n-1} + \dots + a_1 x + a_0 \)
- **Rational function**: \( f(x) = \frac{P(x)}{Q(x)} \), where \( P(x) \) and \( Q(x) \) are polynomials
- **Root function**: \( f(x) = \sqrt[n]{x} \) (e.g., square root: \( \sqrt{x} \))

### 1.2. Exponential and Logarithmic Functions
- **Exponential function**: \( f(x) = a^x \)
- **Natural exponential function**: \( f(x) = e^x \)
- **Logarithmic function**: \( f(x) = \log_b x \)
- **Natural logarithm**: \( f(x) = \ln x \)
- **Common logarithm**: \( f(x) = \log_{10} x \)

### 1.3. Trigonometric Functions
- **Sine function**: \( \sin x \)
- **Cosine function**: \( \cos x \)
- **Tangent function**: \( \tan x \)
- **Cosecant function**: \( \csc x = \frac{1}{\sin x} \)
- **Secant function**: \( \sec x = \frac{1}{\cos x} \)
- **Cotangent function**: \( \cot x = \frac{1}{\tan x} \)

### 1.4. Inverse Trigonometric Functions
- **Arcsine**: \( \sin^{-1} x \) or \( \arcsin x \)
- **Arccosine**: \( \cos^{-1} x \) or \( \arccos x \)
- **Arctangent**: \( \tan^{-1} x \) or \( \arctan x \)
- **Arccosecant**: \( \csc^{-1} x \) or \( \arccsc x \)
- **Arcsecant**: \( \sec^{-1} x \) or \( \arcsec x \)
- **Arccotangent**: \( \cot^{-1} x \) or \( \arccot x \)

### 1.5. Hyperbolic Functions
- **Hyperbolic sine**: \( \sinh x = \frac{e^x - e^{-x}}{2} \)
- **Hyperbolic cosine**: \( \cosh x = \frac{e^x + e^{-x}}{2} \)
- **Hyperbolic tangent**: \( \tanh x = \frac{\sinh x}{\cosh x} \)

### 1.6. Inverse Hyperbolic Functions
- **Inverse hyperbolic sine**: \( \sinh^{-1} x \)
- **Inverse hyperbolic cosine**: \( \cosh^{-1} x \)
- **Inverse hyperbolic tangent**: \( \tanh^{-1} x \)

## 2. Special Functions

### 2.1. Gamma and Related Functions
- **Gamma function**: \( \Gamma(x) = \int_0^\infty t^{x-1} e^{-t} dt \)
- **Beta function**: \( B(x,y) = \int_0^1 t^{x-1} (1 - t)^{y-1} dt \)

### 2.2. Error and Sigmoid Functions
- **Error function**: \( \operatorname{erf}(x) = \frac{2}{\sqrt{\pi}} \int_0^x e^{-t^2} dt \)
- **Sigmoid function**: \( \sigma(x) = \frac{1}{1+e^{-x}} \)

## 3. Discrete and Combinatorial Functions
- **Factorial**: \( n! = 1 \cdot 2 \cdot \dots \cdot n \)
- **Binomial coefficient**: \( \binom{n}{k} = \frac{n!}{k!(n-k)!} \)
- **Fibonacci sequence**: \( F_n = F_{n-1} + F_{n-2} \) with \( F_0 = 0, F_1 = 1 \)

## 4. Probability and Statistics Functions
- **Probability density function (PDF)**: \( f(x) \)
- **Cumulative distribution function (CDF)**: \( F(x) = P(X \leq x) \)
- **Normal distribution function**: \( f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x - \mu)^2}{2\sigma^2}} \)

## 5. Optimization and Transform Functions
- **Fourier transform**: \( F(\omega) = \int_{-\infty}^{\infty} f(x)e^{-i\omega x}dx \)
- **Laplace transform**: \( F(s) = \int_{0}^{\infty} f(t)e^{-st}dt \)

