// ======================================================================
// \title  MathSenderTester.cpp
// \author cindy
// \brief  cpp file for MathSender component test harness implementation class
// ======================================================================

#include "MathSenderTester.hpp"

namespace MathModule {

  // ----------------------------------------------------------------------
  // Construction and destruction
  // ----------------------------------------------------------------------

  MathSenderTester ::
    MathSenderTester() :
      MathSenderGTestBase("MathSenderTester", MathSenderTester::MAX_HISTORY_SIZE),
      component("MathSender")
  {
    this->initComponents();
    this->connectPorts();
  }

  MathSenderTester ::
    ~MathSenderTester()
  {

  }

  // ----------------------------------------------------------------------
  // Tests
  // ----------------------------------------------------------------------

  void MathSenderTester ::
    toDo()
  {
    // TODO
  }

  void MathSenderTester :: 
    testDoMath(MathOp op)
  {
    // Pick values
    const F32 val1 = 2.0;
    const F32 val2 = 3.0;

    // Send the command and pick command sequence number
    const U32 cmdSeq = 10;
  }

}
