// ======================================================================
// \title  MathReceiver.hpp
// \author cindy
// \brief  hpp file for MathReceiver component implementation class
// ======================================================================

#ifndef MathModule_MathReceiver_HPP
#define MathModule_MathReceiver_HPP

#include "Components/MathReceiver/MathReceiverComponentAc.hpp"

namespace MathModule {

  class MathReceiver :
    public MathReceiverComponentBase
  {

    public:

      // ----------------------------------------------------------------------
      // Component construction and destruction
      // ----------------------------------------------------------------------

      //! Construct MathReceiver object
      MathReceiver(
          const char* const compName //!< The component name
      );

      //! Destroy MathReceiver object
      ~MathReceiver();

    PRIVATE:

      // ----------------------------------------------------------------------
      // Handler implementations for typed input ports
      // ----------------------------------------------------------------------

      //! Handler implementation for mathOpIn
      //!
      //! Port for receiving the math operation
      void mathOpIn_handler(
          const NATIVE_INT_TYPE portNum, //!< The port number
          F32 val1, //!< The first operand, a 32-bit float
          const MathModule::MathOp& op, //!< The operation, enum defined in Types/MathTypes.fpp
          F32 val2 //!< The second operand
      ) override;

      //! Handler implementation for schedIn
      //!
      //! The rate group scheduler input
      void schedIn_handler(
          const NATIVE_INT_TYPE portNum, //!< The port number
          NATIVE_UINT_TYPE context //!< The call order
      ) override;

      void parameterUpdated(
          FwPrmIdType id
      ) override;

    PRIVATE:

      // ----------------------------------------------------------------------
      // Handler implementations for commands
      // ----------------------------------------------------------------------

      //! Handler implementation for command CLEAR_EVENT_THROTTLE
      //!
      //! Clear the event throttle
      void CLEAR_EVENT_THROTTLE_cmdHandler(
          const FwOpcodeType opCode, //!< The opcode
          const U32 cmdSeq //!< The command sequence number
      ) override;
  };

}

#endif
