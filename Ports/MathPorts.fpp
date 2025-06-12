# In MathPorts.fpp

module MathModule {
    @ Port for requesting an operation on two numbers
    port OpRequest(
        val1: F32 @< The first operand, a 32-bit float
        op: MathOp @< The operation, enum defined in Types/MathTypes.fpp
        val2: F32 @< The second operand
    )

    @ Port for returning the result of a math operation
    port MathResult(
        result: F32 @< The result of the operation
    )
}