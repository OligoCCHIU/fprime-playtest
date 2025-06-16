// ======================================================================
// \title  MathSenderTester.hpp
// \author cindy
// \brief  hpp file for MathSender component test harness implementation class
// ======================================================================

#ifndef MathModule_MathSenderTester_HPP
#define MathModule_MathSenderTester_HPP

#include "MathSenderGTestBase.hpp"
#include "Components/MathSender/MathSender.hpp"

namespace MathModule {

  class MathSenderTester :
    public MathSenderGTestBase
  {

    public:

      // ----------------------------------------------------------------------
      // Constants
      // ----------------------------------------------------------------------

      // Maximum size of histories storing events, telemetry, and port outputs
      static const FwSizeType MAX_HISTORY_SIZE = 10;

      // Instance ID supplied to the component instance under test
      static const FwEnumStoreType TEST_INSTANCE_ID = 0;

      // Queue depth supplied to the component instance under test
      static const FwSizeType TEST_INSTANCE_QUEUE_DEPTH = 10;

    public:

      // ----------------------------------------------------------------------
      // Construction and destruction
      // ----------------------------------------------------------------------

      //! Construct object MathSenderTester
      MathSenderTester();

      //! Destroy object MathSenderTester
      ~MathSenderTester();

    public:

      // ----------------------------------------------------------------------
      // Tests
      // ----------------------------------------------------------------------

      //! To do
      void toDo();

      void testDoMath(MathOp op);

    private:

      // ----------------------------------------------------------------------
      // Helper functions
      // ----------------------------------------------------------------------

      //! Connect ports
      void connectPorts();

      //! Initialize components
      void initComponents();

    private:

      // ----------------------------------------------------------------------
      // Member variables
      // ----------------------------------------------------------------------

      //! The component under test
      MathSender component;

  };

}

#endif
