module MathModule {
    @ Active component used for sending operations and operands to the MathReceiver.
    active component MathSender {

        # ---------------------------------------------------------------------------
        # General Ports
        # These are user-defined ports for application-specific functions
        # ---------------------------------------------------------------------------

        @ Port for sending the operation request
        output port mathOpOut: OpRequest

        @ Port for receiving the result
        async input port mathResultIn: MathResult

        # ---------------------------------------------------------------------------
        # Special Ports
        # Ports for registering commands with the dispatcher, receiving commands, 
        # sending command responses, emitting event reports, emitting telemetry, time
        # ---------------------------------------------------------------------------

        @ Command recieve port
        command recv port cmdIn

        @ Command registration port
        command reg port cmdRegOut

        @ Command response port
        command resp port cmdResponseOut

        @ Event port
        event port eventOut

        @ Telemetry port
        telemetry port tlmOut

        @ Text event port
        text event port textEventOut

        @ Time get port
        time get port timeGetOut

        # ---------------------------------------------------------------------------
        # Commands
        # Sent from ground or from sequencer, dispatched to this component. Commands
        # that arrive are put in a queue and handler is later run on a thread of
        # this component
        # ---------------------------------------------------------------------------

        @ Do a math operation
        async command DO_MATH(
            val1: F32 @< The first operand, 32-bit float
            op: MathOp @< The operation
            val2: F32 @< The second operand, 32-bit float
        )

        # ---------------------------------------------------------------------------
        # Events
        # Reports that this component can emit, can receive command or a result
        # ---------------------------------------------------------------------------

        @ Math command received
        event COMMAND_RECV(
            val1: F32 @< The first operand
            op: MathOp @< The operation
            val2: F32 @< The second operand
        ) \
        severity activity low \
        format "Math command received: {f} {} {f}"

        @ Received math result
        event RESULT(
            result: F32 @< The math result
        ) \
        severity activity high \
        format "Math result is {f}"

        # ---------------------------------------------------------------------------
        # Telemetry
        # Define telemetry points that component can emit
        # ---------------------------------------------------------------------------

        @ The first value
        telemetry VAL1: F32
        
        @ The operation
        telemetry OP: MathOp

        @ The second value
        telemetry VAL2: F32

        @ The result
        telemetry RESULT: F32

    }
}