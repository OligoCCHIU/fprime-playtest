// ======================================================================
// \title  MathReceiver.cpp
// \author cindy
// \brief  cpp file for MathReceiver component implementation class
// ======================================================================

#include "Components/MathReceiver/MathReceiver.hpp"

namespace MathModule {

  // ----------------------------------------------------------------------
  // Component construction and destruction
  // ----------------------------------------------------------------------

  MathReceiver ::
    MathReceiver(const char* const compName) :
      MathReceiverComponentBase(compName)
  {

  }

  MathReceiver ::
    ~MathReceiver()
  {

  }

  // ----------------------------------------------------------------------
  // Handler implementations for typed input ports
  // ----------------------------------------------------------------------

  /*
    MathOpIn_Handler does the following:
      1. Compute an initial result based on the input values and the requested operation.
      2. Get the value of the factor parameter. Check that the value is a valid value
         from the parameter database or a default parameter value.
      3. Multiply the initial result by the factor to generate the final result.
      4. Emit telemetry and events.
      5. Emit the results.
  */
  void MathReceiver ::
    mathOpIn_handler(
        const NATIVE_INT_TYPE portNum,
        F32 val1,
        const MathModule::MathOp& op,
        F32 val2
    )
  {
    // Get the initial result
    F32 res = 0.0;

    switch(op.e) {
      case MathOp::ADD:
        res = val1 + val2;
        break;
      case MathOp::SUB:
        res = val1 - val2;
        break;
      case MathOp::DIV:
        res = val1 / val2;
        break;
      case MathOp::MUL:
        res = val1 * val2;
        break;
      default:
        FW_ASSERT(0, op.e);
        break;
    } // end of switch

    // Get the factor value
    Fw::ParamValid valid;
    F32 factor = paramGet_FACTOR(valid);
    FW_ASSERT(
      valid.e == Fw::ParamValid::VALID || valid.e == Fw::ParamValid::DEFAULT, 
      valid.e
    );

    // Multiply result by factor
    res *= factor;

    // Emit telemetry and events
    this->log_ACTIVITY_HI_OPERATION_PERFORMED(op);
    this->tlmWrite_OPERATION(op);

    // Emit result
    this->mathResultOut_out(0, res);
  }

  /*
    schedIn_handler dispatches all the messages in the queue. 
    For queued components, we have to do this dispatch explicitly in the
    schedIn_handler.
  */
  void MathReceiver ::
    schedIn_handler(
        const NATIVE_INT_TYPE portNum,
        NATIVE_UINT_TYPE context
    )
  {
    U32 numMsgs = this->m_queue.getMessagesAvailable();
    for (U32 i = 0; i < numMsgs; ++i)
    {
      (void) this->doDispatch();
    }
  }

  /*
    parameterUpdated is an optional function that, if present, is called when a
    parameter is updated by command

    if parameter identifier is PARAMID_FACTOR - get parameter value and emit event report
    otherwise, fail assertion, code will not run
  */
 void MathReceiver ::
  parameterUpdated(FwPrmIdType id)
  {
    switch(id){
      case PARAMID_FACTOR:{
        Fw::ParamValid valid;
        F32 val = this->paramGet_FACTOR(valid);
        FW_ASSERT(
          valid.e == Fw::ParamValid::VALID || valid.e == Fw::ParamValid::DEFAULT,
          valid.e
        );
        this->log_ACTIVITY_HI_FACTOR_UPDATED(val);
        break;
      }
      default:
        FW_ASSERT(0, id);
        break;
    }
  }

  // ----------------------------------------------------------------------
  // Handler implementations for commands
  // ----------------------------------------------------------------------

  /*
    CLEAR_EVENT_THROTTLE_cmdHandler clears the throttling of the FACTOR_UPDATED
    event and the next two lines send a notification event and sends a command response.
  */
  void MathReceiver ::
    CLEAR_EVENT_THROTTLE_cmdHandler(
        const FwOpcodeType opCode,
        const U32 cmdSeq
    )
  {
    // clear throttle
    this->log_ACTIVITY_HI_FACTOR_UPDATED_ThrottleClear();
    // send event that throttle is cleared
    this->log_ACTIVITY_HI_THROTTLE_CLEARED();
    // reply with completion status
    this->cmdResponse_out(opCode, cmdSeq, Fw::CmdResponse::OK);
  }
}
