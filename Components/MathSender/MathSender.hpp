// ======================================================================
// \title  MathSender.hpp
// \author cindy
// \brief  hpp file for MathSender component implementation class
// ======================================================================

#ifndef MathModule_MathSender_HPP
#define MathModule_MathSender_HPP

#include "Components/MathSender/MathSenderComponentAc.hpp"

namespace MathModule {

  class MathSender :
    public MathSenderComponentBase
  {

    public:

      // ----------------------------------------------------------------------
      // Component construction and destruction
      // ----------------------------------------------------------------------

      //! Construct MathSender object
      MathSender(
          const char* const compName //!< The component name
      );

      //! Destroy MathSender object
      ~MathSender();

    PRIVATE:

      // ----------------------------------------------------------------------
      // Handler implementations for typed input ports
      // ----------------------------------------------------------------------

      //! Handler implementation for mathResultIn
      //!
      //! Port for receiving the result
      void mathResultIn_handler(
          const NATIVE_INT_TYPE portNum, //!< The port number
          F32 result //!< The result of the operation
      ) override;

    PRIVATE:

      // ----------------------------------------------------------------------
      // Handler implementations for commands
      // ----------------------------------------------------------------------

      //! Handler implementation for command DO_MATH
      //!
      //! Do a math operation
      void DO_MATH_cmdHandler(
          const FwOpcodeType opCode, //!< The opcode
          const U32 cmdSeq, //!< The command sequence number
          F32 val1, //!< The first operand, 32-bit float
          MathModule::MathOp op, //!< The operation
          F32 val2 //!< The second operand, 32-bit float
      ) override;

  };

}

#endif
