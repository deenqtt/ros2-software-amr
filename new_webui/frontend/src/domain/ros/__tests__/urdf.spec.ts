import { describe, expect, it } from 'vitest'
import { parseUrdfFootprint } from '../urdf'

const boxUrdf = `
<robot name="amr">
  <link name="base_footprint">
    <visual><geometry><box size="0.9 0.5 0.2"/></geometry></visual>
    <collision><geometry><box size="0.8 0.6 0.2"/></geometry></collision>
  </link>
</robot>`

const cylinderUrdf = `
<robot name="amr">
  <link name="base_link">
    <collision><geometry><cylinder radius="0.25" length="0.3"/></geometry></collision>
  </link>
</robot>`

describe('parseUrdfFootprint', () => {
  it('prefers collision geometry over visual', () => {
    expect(parseUrdfFootprint(boxUrdf)).toEqual({ length: 0.8, width: 0.6 })
  })

  it('falls back to visual geometry when there is no collision box', () => {
    const urdf = `
      <robot name="amr">
        <link name="base_footprint">
          <visual><geometry><box size="1.2 0.7 0.2"/></geometry></visual>
        </link>
      </robot>`
    expect(parseUrdfFootprint(urdf)).toEqual({ length: 1.2, width: 0.7 })
  })

  it('derives a square footprint from a cylinder', () => {
    expect(parseUrdfFootprint(cylinderUrdf)).toEqual({ length: 0.5, width: 0.5 })
  })

  it('returns null for empty, malformed or footprint-less input', () => {
    expect(parseUrdfFootprint('')).toBeNull()
    expect(parseUrdfFootprint('<robot><link name="wheel"/></robot>')).toBeNull()
    expect(parseUrdfFootprint('not xml at all <<<')).toBeNull()
  })

  it('rejects non-positive and non-numeric dimensions', () => {
    expect(
      parseUrdfFootprint('<robot><link name="base_link"><collision><geometry><box size="0 1 1"/></geometry></collision></link></robot>'),
    ).toBeNull()
    expect(
      parseUrdfFootprint('<robot><link name="base_link"><collision><geometry><box size="a b c"/></geometry></collision></link></robot>'),
    ).toBeNull()
    expect(
      parseUrdfFootprint('<robot><link name="base_link"><collision><geometry><cylinder radius="-1"/></geometry></collision></link></robot>'),
    ).toBeNull()
  })
})
